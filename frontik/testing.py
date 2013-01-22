"""

# configure service mocks
routes = [
    ('route_name', r'url_path', service_mock_function),
    ('vacancy_search', r'/SearchService/VacancySearch', post_proto_search)
]

# config is a frontik config stub
test_env = frontik.testing.TestEnvironment(module, test_module, routes, config,
    # here come additional properties for PageHandler object and common headers
    session=applicant_session, headers={'X-HH-Snapshot': 'TEST-SNAPSHOT'})

app = test_env.create_test_app(more_handler_properties={})

# this method will be called inside get_page/post_page of a test app
def __tested(handler):
    pass

response = app.call(__tested, data={}, headers={})
assert response.code == 200
assert app.called_once('vacancy_search')

# we can test http_request/http_response pairs as well

http_request = Get('/search_vacancy', data_dict, headers_dict)
response = app.send_request(http_request)

assert response.code == 200

"""

from collections import defaultdict, namedtuple
import functools
import inspect
import logging
import os
import re
from urlparse import urlparse
import time
import cStringIO
from lxml import etree
import tornado.options
from tornado.ioloop import IOLoop
from tornado.web import Application
from tornado.httpclient import HTTPResponse
from tornado.httpclient import HTTPRequest as HTTPClientRequest
from tornado.httpserver import HTTPRequest as HTTPServerRequest
import sys
import copy

import frontik.app
import frontik.async
import frontik.handler
import frontik.handler_xml
import frontik.jobs
import frontik.options
import frontik.doc
import frontik.magic_imp

frontik_testing_logger = logging.getLogger('frontik.testing')


class GeneralStub(object):
    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)


class HTTPResponseWrapper(HTTPResponse):
    def __init__(self, request, code, headers=None, buffer=None, **kwargs):
        headers = {} if headers is None else headers
        buffer = cStringIO.StringIO(buffer)
        super(HTTPResponseWrapper, self).__init__(request, code, headers, buffer, **kwargs)

class HTTPRequestWrapper(HTTPServerRequest):
    def __init__(self, method, url, data, **kwargs):
        uri = frontik.util._encode(frontik.util.make_url(url, **data))
        super(HTTPRequestWrapper, self).__init__(method, uri, remote_ip='127.0.0.1', **kwargs)

        del self.connection
        self.write = lambda c: frontik_testing_logger.debug('Mocked HTTPRequest.write called, doing nothing')
        self.finish = lambda: frontik_testing_logger.debug('Mocked HTTPRequest.finish called, doing nothing')

class Request(object):
    def __init__(self, url, data=None, headers=None):
        self.data, self.headers = (x if x is not None else {} for x in (data, headers))
        self.url = url

    def get_server_request(self):
        return HTTPRequestWrapper(self.method, self.url, self.data, headers=self.headers)

    def get_client_request(self):
        return self.client_request_factory(self.url, self.data, headers=self.headers)

class Get(Request):
    method = 'GET'
    handler_method = 'get_page'
    client_request_factory = functools.partial(frontik.util.make_get_request)

class Post(Request):
    method = 'POST'
    handler_method = 'post_page'
    client_request_factory = functools.partial(frontik.util.make_post_request)


class TestApp(object):

    FILE_EXT_TO_CONTENT_TYPE = dict(
        xml='text/xml', json='text/json'
    )

    def __init__(self, module, test_module, routes, default_headers, handler_params, ph_globals):
        self.module = module
        self.test_module = test_module
        self.default_headers = default_headers
        self.handler_params = handler_params
        self.ph_globals = ph_globals

        self.async_callbacks = []
        self.routes = routes
        self.routes_called = defaultdict(int)
        self.saved_responses = defaultdict(list)
        self.exceptions = []

    def set_mock(self, route_name, mock_source):
        route_regex, route_mock = self.routes[route_name]
        self.routes[route_name] = (route_regex, mock_source)

    def call(self, function, *function_args, **function_kwargs):
        caller_method = inspect.stack()[1][3]
        data = function_kwargs.pop('data', {})
        headers = dict(self.default_headers, **function_kwargs.pop('headers', {}))
        request = Get('/' + caller_method, data, headers=headers)

        create_handler = functools.partial(self.__create_page_handler, frontik.handler.PageHandler, 'get_page',
            function, function_args, function_kwargs)
        return self.__get_response_from_handler(request, create_handler)

    def send_request(self, request):
        module_name = 'pages.' + '.'.join(request.url.strip('/').split('/'))
        importer = frontik.magic_imp.FrontikAppImporter(self.module.__name__, os.path.dirname(self.module.__file__))
        handler_class = importer.imp_app_module(module_name).Page
        method = getattr(handler_class, request.handler_method)

        request.headers = dict(self.default_headers, **request.headers)
        create_handler = functools.partial(self.__create_page_handler, handler_class, request.handler_method, method, [], {})
        response = self.__get_response_from_handler(request, create_handler)

        self.__save_test_pair(request, response, inspect.stack()[1][3])
        return response

    def __get_response_from_handler(self, request, create_handler):
        app = Application([(r'/.*', create_handler, dict(ph_globals=self.ph_globals))])
        handler = app(request.get_server_request())

        return HTTPResponse(request.get_client_request(), code=handler._status_code, headers=self.saved_headers,
            buffer=cStringIO.StringIO(''.join(self.saved_buffer)))

    def called_once(self, route_name):
        return self.get_call_count(route_name) == 1

    def not_called(self, route_name):
        return self.get_call_count(route_name) == 0

    def get_call_count(self, route_name):
        return self.routes_called[route_name]

    def response_for(self, route_name):
        responses = self.saved_responses[route_name]
        return responses if len(responses) > 1 else responses[0]

    def __create_page_handler(self, handler_class, handler_method_name, function,
                              function_args, function_kwargs, *handler_args, **handler_kwargs):

        IOLoop.instance().add_callback = lambda x: self.async_callbacks.append((x, lambda: tuple()))

        def __controller():
            function(handler, *function_args, **function_kwargs)
            self.__execute_callbacks()
            self.__reraise_exceptions()

        def __stack_context_handle_exception(type, value, traceback):
            try:
                handler_stack_context_handle_exception_orig(type, value, traceback)
            except Exception, e:
                self.__add_exception(e)

        def __flush(include_footers=False):
            self.saved_buffer = handler._write_buffer
            self.saved_headers = handler._headers
            handler_flush_orig(include_footers)

        self.saved_buffer = []
        self.saved_headers = {}

        handler = handler_class(*handler_args, **handler_kwargs)
        handler_flush_orig = handler.flush
        handler_stack_context_handle_exception_orig = handler._stack_context_handle_exception

        for name, value in self.handler_params.items():
            setattr(handler, name, value)

        setattr(handler, handler_method_name, __controller)
        handler.http_client = GeneralStub(fetch=self.__http_client_fetch)
        handler.flush = __flush
        handler._stack_context_handle_exception = __stack_context_handle_exception
        return handler

    def __http_client_fetch(self, request, callback, **kwargs):
        if not isinstance(request, HTTPClientRequest):
            request = HTTPClientRequest(url=request, **kwargs)
        self.__add_callback(request, dict(started=time.time()), callback)

    def __add_callback(self, request, request_info, callback):
        route_url = urlparse(request.url).path
        for route_name, (regex, route_source) in self.routes.iteritems():
            match = re.match(r'.+{0}/?$'.format(regex), route_url)
            if match:
                frontik_testing_logger.debug('Call to {url} will be mocked'.format(url=request.url))
                self.__add_route_callback(callback, route_name,
                    functools.partial(self.__get_load_function(route_source), request, request_info))
                return

        raise NotImplementedError('Url {url} is not mocked'.format(url=route_url))

    def __add_route_callback(self, callback, route_name, route_function):
        self.routes_called[route_name] += 1
        self.async_callbacks.append((callback, route_name, route_function))
        frontik_testing_logger.debug('Callback added, {0} total'.format(len(self.async_callbacks)))

    def __execute_callbacks(self):
        while self.async_callbacks:
            cb, route_name, route_fn = self.async_callbacks.pop()
            frontik_testing_logger.debug('Executing callback, {0} left'.format(len(self.async_callbacks)))

            try:
                response = route_fn()
                self.saved_responses[route_name].append(response)
                cb(response)
            except Exception, e:
                self.__add_exception(sys.exc_info())
                frontik_testing_logger.debug('Callback raised exception: {0}'.format(e))

    def __add_exception(self, exc_info):
        self.exceptions.append(exc_info)

    def __reraise_exceptions(self):
        while self.exceptions:
            exc_info = self.exceptions.pop()
            raise exc_info[1], None, exc_info[2]

    TEST_FILE_TEMPLATE = os.linesep.join([
        '# coding=utf-8',
        '# This is autogenerated test result file',
        'request = dict(method="{req.method}", url="{req.url}", data={req.data}, headers={req.headers})',
        'response = dict(code="{res.code}", body="""{res_body}""", headers={res.headers})'])

    def __get_load_function(self, route_source):
        mocks_dir = os.path.join(os.path.dirname(self.test_module.__file__), 'mocks', 'services')

        def __response_from_file(file):
            _, file_ext = os.path.splitext(file)

            @service_response(self.FILE_EXT_TO_CONTENT_TYPE[file_ext[1:]])
            def _load_fn(response):
                return 200, open(os.path.join(mocks_dir, file)).read()

            return _load_fn

        if isinstance(route_source, basestring):
            return __response_from_file(route_source)
        elif callable(route_source):
            return route_source
        else:
            raise ValueError('Cannot use route %s' % route_source)

    def __save_test_pair(self, request, response, caller_method):
        def __create_init_py(dir):
            open(os.path.join(dir, '__init__.py'), 'a').close()

        tests_dir = os.path.join(os.path.dirname(self.test_module.__file__), 'mocks', 'generated')
        if not os.path.exists(tests_dir):
            os.mkdir(tests_dir)
            __create_init_py(tests_dir)

        url_tests_dir = os.path.join(tests_dir, request.url.strip('/'))
        if not os.path.exists(url_tests_dir):
            os.mkdir(url_tests_dir)
            __create_init_py(url_tests_dir)

        test_file = os.path.join(url_tests_dir, caller_method + '.py')

        response_type = response.headers.get('Content-Type', 'text/html')
        if response_type == 'text/xml':
            response_body = etree.tostring(etree.fromstring(response.body), pretty_print=True)
        else:
            response_body = response.body

        with open(test_file, 'w') as f:
            f.write(self.TEST_FILE_TEMPLATE.format(req=request, res=response, res_body=response_body))


class TestEnvironment(object):
    def __init__(self, module, test_module, routes, config, **kwargs):
        tornado.options.process_options_logging()
        self.module = module
        self.test_module = test_module
        self.routes = routes
        self.default_headers = kwargs.pop('headers', {})
        self.default_params = kwargs
        self.ph_globals = frontik.handler.PageHandlerGlobals(GeneralStub(config=config))

    def create_test_app(self, **kwargs):
        params = dict(self.default_params, **kwargs)
        return TestApp(self.module, self.test_module, copy.deepcopy(self.routes), self.default_headers, params, self.ph_globals)


def service_response(response_type):
    def __wrapper(func):
        def __internal(request, request_info):
            result = func(request)

            if isinstance(result, HTTPResponse):
                response = result
            else:
                if isinstance(result, tuple):
                    code, response_body = result
                elif isinstance(result, basestring):
                    code, response_body = 200, result
                else:
                    raise ValueError('Cannot parse response returned by mock function')

                if response_type == 'application/x-protobuf':
                    response_body = response_body.SerializeToString()

                response = HTTPResponseWrapper(request, code, headers={'Content-Type': response_type},
                    buffer=response_body)

            response.request_time = time.time() - request_info['started']
            return response

        return __internal

    return __wrapper

@service_response('text/xml')
def empty_xml_500(request):
    return 500, ''

@service_response('text/xml')
def empty_xml_403(request):
    return 403, ''

@service_response('text/plain')
def empty_text_200(request):
    return ''
