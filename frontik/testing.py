from collections import defaultdict, namedtuple
from functools import partial
import inspect
import logging
import re
from urlparse import urlparse
from tornado.web import Application
from tornado.httpclient import HTTPResponse
from tornado.httpserver import HTTPRequest as HTTPServerRequest
from lxml import etree
import sys

import frontik.app
import frontik.async
import frontik.handler
import frontik.handler_xml
import frontik.jobs
import frontik.options
import frontik.doc

frontik_testing_logger = logging.getLogger('frontik.testing')
frontik_testing_logger.addHandler(logging.StreamHandler(strm=sys.stdout))

frontik_testing_logger.process_stages = lambda x: None
frontik_testing_logger.stage_tag = lambda x: None

class GeneralStub(object):
    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)

class HTTPRequestWrapper(HTTPServerRequest):
    def __init__(self, method, url, data, **kwargs):
        uri = frontik.util._encode(frontik.util.make_url(url, **data))
        super(HTTPRequestWrapper, self).__init__(method, uri, remote_ip='127.0.0.1', **kwargs)

        del self.connection
        self.write = lambda c: None
        self.finish = lambda: None

class HTTPResponseWrapper(HTTPResponse):
    @property
    def body(self):
        return self._body

    @body.setter
    def body(self, body):
        self._body = body

class PageHandlerReplacement(frontik.handler.PageHandler):
    def __init__(self, wrapper, handler_params, *args, **kwargs):
        super(PageHandlerReplacement, self).__init__(*args, **kwargs)

        for name, value in handler_params.items():
            setattr(self, name, value)

        self.log = frontik_testing_logger
        self.wrapper = wrapper
        self.saved_buffer = []
        self.saved_headers = {}

    # Methods replacements

    def get_url(self, url, data=None, callback=None, **kwargs):
        request = frontik.util.make_get_request(url, data, kwargs.get('headers', None))
        self.__fetch_url(request, data, callback, **kwargs)

    def post_url(self, url, data=None, callback=None, **kwargs):
        request = frontik.util.make_post_request(url, data, kwargs.get('headers', None))
        self.__fetch_url(request, data, callback, **kwargs)

    def put_url(self, url, data=None, callback=None, **kwargs):
        request = frontik.util.make_put_request(url, data, kwargs.get('headers', None))
        self.__fetch_url(request, data, callback, **kwargs)

    def delete_url(self, url, data=None, callback=None, **kwargs):
        request = frontik.util.make_delete_request(url, data, kwargs.get('headers', None))
        self.__fetch_url(request, data, callback, **kwargs)

    def __fetch_url(self, request, data_dict=None, callback=None, **kwargs):
        self.wrapper.add_callback(request, data_dict if data_dict is not None else {}, callback)

    def _stack_context_handle_exception(self, type, value, traceback):
        try:
            super(PageHandlerReplacement, self)._stack_context_handle_exception(type, value, traceback)
        except Exception, e:
            self.wrapper.add_exception(e)

    def flush(self, include_footers=False):
        self.saved_buffer = self._write_buffer
        self.saved_headers = self._headers
        super(PageHandlerReplacement, self).flush(include_footers)

class TestApp(object):
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
            return handler

        app = Application([(r'/.*', __create_page_handler, dict(ph_globals=self.ph_globals))])
        handler = app(self.request)

        http_client_request = frontik.util.make_get_request(self.request.uri)
        response = HTTPResponseWrapper(http_client_request, code=handler._status_code, headers=handler.saved_headers)
        response.body = ''.join(handler.saved_buffer)
        return response

    def called_once(self, route):
        return self.get_call_count(route) == 1

    def not_called(self, route):
        return self.get_call_count(route) == 0

    def get_call_count(self, route):
        return self.routes_called[route]

    def add_callback(self, request, data_dict, callback):
        route_url = urlparse(request.url).path
        for route_name, regex, route in self.routes:
            match = re.match(r'.+{0}/?$'.format(regex), route_url)
            if match:
                frontik_testing_logger.debug('Call to {url} will be mocked'.format(url=request.url))
                self.__add_route_callback(callback, route_name,
                    partial(route, request, data_dict, **dict(match.groupdict(), **self.routes_data[route_name])))
                return

        raise NotImplementedError('Url "{url}" is not mocked'.format(url=route_url))

    def __add_route_callback(self, callback, route_name, route_function):
        self.routes_called[route_name] += 1
        self.async_callbacks.append((callback, route_function))
        frontik_testing_logger.debug('Callback added, {0} total'.format(len(self.async_callbacks)))

    def __execute_callbacks(self):
        while self.async_callbacks:
            cb, route = self.async_callbacks.pop()
            frontik_testing_logger.debug('Executing callback, {0} left'.format(len(self.async_callbacks)))

            try:
                cb(*route())
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

        self.routes = routes
        self.handler_default_params = kwargs
        self.ph_globals = frontik.handler.PageHandlerGlobals(GeneralStub(config=config))

    def new_test_app(self, **kwargs):
        """
            kwargs can contain any properties that should be overriden in this particular handler
            'query' and 'headers' are used to build HTTPRequest object for the handler
        """

        caller_method = inspect.stack()[1][3]
        request = HTTPRequestWrapper('GET', '/' + caller_method, kwargs.pop('query', {}), headers=kwargs.pop('headers', {}))
        handler_params = dict(self.handler_default_params, **kwargs)
        return TestApp(self.routes, request, handler_params, self.ph_globals)


Get = namedtuple('Get', ('url', 'data'))
Post = namedtuple('Post', ('url', 'data'))

class FrontikAppRequestMocker(object):

    PageMethodsMapping = {
        Get: 'get_page',
        Post: 'post_page'
    }

    def serve_request(self, app, request):
        method_name = self.PageMethodsMapping.get(request.__class__, self.PageMethodsMapping[Get])
        module_name = 'pages.' + '.'.join(request.url.strip('/').split('/'))
        method = frontik_import(module_name).Page.__dict__[method_name]

        return app.call(method)


def service_response(response_type):
    def __wrapper(func):
        def __internal(request, data_dict, *args, **kwargs):
            result = func(request.url, data_dict, *args, **kwargs)

            if isinstance(result, tuple):
                response_body, response = result
            else:
                response_body = result
                response = HTTPResponseWrapper(request, code=200)

            if response_type == 'text/xml':
                response.headers['Content-Type'] = 'text/xml'
                response_body = etree.fromstring(response_body)
            elif response_type == 'application/x-protobuf':
                response.headers['Content-Type'] = 'application/x-protobuf'
                response_body = response_body.SerializeToString()

            response.body = response_body
            return response_body, response

        return __internal

    return __wrapper
