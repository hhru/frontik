"""

# configure service mocks
routes = [
    ('route_name', r'url_path', service_mock_function),
    ('vacancy_search', r'/SearchService/VacancySearch', post_proto_search)
]

# config is a frontik config stub
test_env = frontik.testing.TestEnvironment(routes, config,
    # here come additional parameters for PageHandler object or HTTPRequest (query and headers)
    session=applicant_session, headers={'X-HH-Snapshot': 'TEST-SNAPSHOT'})

app = test_env.create_test_app()

# provide sample data to service mocks
app.set_route_data('vacancy_search', vacancies=vacancies)

# this method will be called inside get_page/post_page of a test app
def __tested(handler):
    pass

response = app.call(__tested)
assert response.code == 200
assert app.called_once('vacancy_search')

# we can test http_request/http_response pairs as well

app = test.create_test_app()
http_request = Get('/search_vacancy', {data: 'data'})
response = app.call_url(http_request)

assert response.code == 200

"""

from collections import defaultdict, namedtuple
from functools import partial
import inspect
import logging
import re
from urlparse import urlparse
import time
import cStringIO
from tornado.web import Application
from tornado.httpclient import HTTPResponse
from tornado.httpclient import HTTPRequest as HTTPClientRequest
from tornado.httpserver import HTTPRequest as HTTPServerRequest
import sys

import frontik.app
import frontik.async
import frontik.handler
import frontik.handler_xml
import frontik.jobs
import frontik.options
import frontik.doc

frontik_testing_logger = logging.getLogger('frontik.testing')

class GeneralStub(object):
    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)

class HTTPRequestWrapper(HTTPServerRequest):
    def __init__(self, method, url, data, **kwargs):
        uri = frontik.util._encode(frontik.util.make_url(url, **data))
        super(HTTPRequestWrapper, self).__init__(method, uri, remote_ip='127.0.0.1', **kwargs)

        del self.connection
        self.write = lambda c: frontik_testing_logger.debug('Mocked HTTPRequest.write called, doing nothing')
        self.finish = lambda: frontik_testing_logger.debug('Mocked HTTPRequest.finish called, doing nothing')

class PageHandlerReplacement(frontik.handler.PageHandler):
    def __init__(self, test_app, handler_params, *args, **kwargs):
        super(PageHandlerReplacement, self).__init__(*args, **kwargs)

        for name, value in handler_params.items():
            setattr(self, name, value)

        self.test_app = test_app
        self.saved_buffer = []
        self.saved_headers = {}

    # Methods replacements

    def _stack_context_handle_exception(self, type, value, traceback):
        try:
            super(PageHandlerReplacement, self)._stack_context_handle_exception(type, value, traceback)
        except Exception, e:
            self.test_app.add_exception(e)

    def flush(self, include_footers=False):
        self.saved_buffer = self._write_buffer
        self.saved_headers = self._headers
        super(PageHandlerReplacement, self).flush(include_footers)


Get = namedtuple('Get', ('url', 'data'))
Post = namedtuple('Post', ('url', 'data'))

class TestApp(object):

    PageMethodsMapping = {
        Get: 'get_page',
        Post: 'post_page'
    }

    def __init__(self, routes, request, handler_params, ph_globals):
        self.request = request
        self.handler_params = handler_params
        self.ph_globals = ph_globals

        self.async_callbacks = []
        self.routes = routes
        self.routes_data = defaultdict(dict)
        self.routes_called = defaultdict(int)
        self.exceptions = []

    def set_route_data(self, route_name, **kwargs):
        self.routes_data[route_name].update(kwargs)

    def call(self, function, *f_args, **f_kwargs):
        def __create_page_handler(*args, **kwargs):
            def __get_page():
                function(handler, *f_args, **f_kwargs)
                self.__execute_callbacks()
                self.__reraise_exceptions()

            handler = PageHandlerReplacement(self, self.handler_params, *args, **kwargs)
            handler.get_page = __get_page
            handler.http_client = GeneralStub(fetch=self.__http_client_fetch)
            return handler

        app = Application([(r'/.*', __create_page_handler, dict(ph_globals=self.ph_globals))])
        handler = app(self.request)

        http_client_request = frontik.util.make_get_request(self.request.uri)
        return HTTPResponse(http_client_request, code=handler._status_code, headers=handler.saved_headers,
            buffer=cStringIO.StringIO(''.join(handler.saved_buffer)))

    def call_url(self, request):
        method_name = self.PageMethodsMapping.get(request.__class__, self.PageMethodsMapping[Get])
        module_name = 'pages.' + '.'.join(request.url.strip('/').split('/'))
        method = frontik_import(module_name).Page.__dict__[method_name]

        return self.call(method)

    def called_once(self, route):
        return self.get_call_count(route) == 1

    def not_called(self, route):
        return self.get_call_count(route) == 0

    def get_call_count(self, route):
        return self.routes_called[route]

    def __http_client_fetch(self, request, callback, **kwargs):
        if not isinstance(request, HTTPClientRequest):
            request = HTTPClientRequest(url=request, **kwargs)
        self.add_callback(request, dict(started=time.time()), callback)

    def add_callback(self, request, request_info, callback):
        route_url = urlparse(request.url).path
        for route_name, regex, route in self.routes:
            match = re.match(r'.+{0}/?$'.format(regex), route_url)
            if match:
                frontik_testing_logger.debug('Call to {url} will be mocked'.format(url=request.url))
                self.__add_route_callback(callback, route_name,
                    partial(route, request, request_info, **dict(match.groupdict(), **self.routes_data[route_name])))
                return

        raise NotImplementedError('Url {url} is not mocked'.format(url=route_url))

    def __add_route_callback(self, callback, route_name, route_function):
        self.routes_called[route_name] += 1
        self.async_callbacks.append((callback, route_function))
        frontik_testing_logger.debug('Callback added, {0} total'.format(len(self.async_callbacks)))

    def __execute_callbacks(self):
        while self.async_callbacks:
            cb, route = self.async_callbacks.pop()
            frontik_testing_logger.debug('Executing callback, {0} left'.format(len(self.async_callbacks)))

            try:
                cb(route())
            except Exception, e:
                self.add_exception(e)
                frontik_testing_logger.debug('Callback raised exception: {0}'.format(e))

    def add_exception(self, e):
        self.exceptions.append(e)

    def __reraise_exceptions(self):
        while self.exceptions:
            raise self.exceptions.pop()

class TestEnvironment(object):
    def __init__(self, routes, config, **kwargs):
        """
            Creates test environment (predefined routes, config and default handler properties)
        """

        self.__bootstrap_logging()

        self.routes = routes
        self.default_params = kwargs
        self.ph_globals = frontik.handler.PageHandlerGlobals(GeneralStub(config=config))

    def create_test_app(self, **kwargs):
        """
            kwargs can contain any properties that should be overriden in this particular handler
            'query' and 'headers' are used to build HTTPRequest object for the handler
        """

        caller_method = inspect.stack()[1][3]
        query = dict(self.default_params.pop('query', {}), **kwargs.pop('query', {}))
        headers = dict(self.default_params.pop('headers', {}), **kwargs.pop('headers', {}))
        params = dict(self.default_params, **kwargs)

        request = HTTPRequestWrapper('GET', '/' + caller_method, query, headers=headers)
        return TestApp(self.routes, request, params, self.ph_globals)

    def __bootstrap_logging(self):
        handlers = logging.getLogger().handlers
        for h in handlers:
            logging.getLogger().removeHandler(h)
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
            format='[%(process)s] %(asctime)s %(levelname)s %(name)s: %(message)s')


def service_response(response_type):
    def __wrapper(func):
        def __internal(request, request_info, *args, **kwargs):
            result = func(request, *args, **kwargs)

            if isinstance(result, tuple):
                response_body, response = result
            else:
                response_body = result
                response = HTTPResponse(request, code=200)

            if response_type == 'text/xml':
                response.headers['Content-Type'] = 'text/xml'
            elif response_type == 'application/x-protobuf':
                response.headers['Content-Type'] = 'application/x-protobuf'
                response_body = response_body.SerializeToString()

            response.request_time = time.time() - request_info['started']
            response.buffer = cStringIO.StringIO(response_body)
            return response

        return __internal

    return __wrapper
