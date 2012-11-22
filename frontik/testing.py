from collections import defaultdict, namedtuple
from functools import partial
import httplib
import logging
import re
from urlparse import urlparse
from tornado.ioloop import IOLoop
from tornado.httpclient import HTTPResponse
from lxml import etree
import sys

import frontik.app
import frontik.async
import frontik.handler
import frontik.options
import frontik.doc
from frontik.handler import HTTPError

frontik_testing_logger = logging.getLogger('frontik.testing')
frontik_testing_logger.addHandler(logging.StreamHandler(strm=sys.stdout))

class GeneralStub(object):
    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)

class HTTPResponseWrapper(HTTPResponse):
    @property
    def body(self):
        return self._body

    @body.setter
    def body(self, body):
        self._body = body

class Mock(object):
    def __init__(self, routes, config, **kwargs):
        self.routes = routes
        self.config = config
        self.handler_default_params = kwargs

    def new_handler(self, **kwargs):
        return HandlerMock(self.routes, self.config, **dict(self.handler_default_params, **kwargs))

class HandlerMock(GeneralStub):

    def __init__(self, routes, config, **kwargs):
        super(HandlerMock, self).__init__(**kwargs)
        self.log = frontik_testing_logger
        self.config = config
        self.xml = GeneralStub(doc=frontik.doc.Doc(root_node = etree.Element('doc', frontik = 'true')))
        self.finish_group = frontik.async.AsyncGroup(lambda: None, name='finish', log=self.log.debug)

        self.async_callbacks = []
        self.routes = routes
        self.routes_data = defaultdict(dict)
        self.routes_called = defaultdict(int)

        if getattr(self, 'cookies', None) is None:
            self.cookies = {}

        if getattr(self, 'request_id', None) is None:
            self.request_id = 'TEST_REQUEST_ID'

        self.request = GeneralStub(
            arguments=kwargs.get('arguments', {}),
            headers=kwargs.get('headers', {}),
            host=kwargs.get('host', '')
        )

        IOLoop._instance = GeneralStub(
            add_callback=lambda x: self.__add_callback(x, 'IOLoop_callback', lambda: [])
        )

    # Mock methods replacements

    def get_arguments(self, name, default=None):
        args = self.request.arguments.get(name, None)
        if args is None:
            return default
        return args if isinstance(args, list) else [args]

    def get_argument(self, name, default=None):
        args = self.get_arguments(name)
        if args is None:
            return default
        return args[-1]

    def get_cookie(self, name, default=None):
        return self.cookies.get(name, default)

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
        if data_dict is None:
            data_dict = {}

        route_url = urlparse(request.url).path
        for route_name, regex, route in self.routes:
            match = re.match(r'.+{0}/?$'.format(regex), route_url)
            if match:
                frontik_testing_logger.debug('Call to {url} will be mocked'.format(url=request.url))
                self.__add_callback(callback, route_name,
                    partial(route, request, data_dict, **dict(match.groupdict(), **self.routes_data[route_name])))
                return

        raise NotImplementedError('Url "{url}" is not mocked'.format(url=route_url))

    # Custom mock methods

    def set_route_data(self, route_name, **kwargs):
        self.routes_data[route_name].update(kwargs)

    def call(self, function, *args, **kwargs):
        function(*args, **kwargs)
        self.__execute_callbacks()

    def called_once(self, route):
        return self.get_call_count(route) == 1

    def not_called(self, route):
        return self.get_call_count(route) == 0

    def get_call_count(self, route):
        return self.routes_called[route]

    def __add_callback(self, callback, route_name, route_function):
        self.routes_called[route_name] += 1
        self.async_callbacks.append((callback, route_function))
        frontik_testing_logger.debug('Callback added, {0} total'.format(len(self.async_callbacks)))

    def __execute_callbacks(self):
        while self.async_callbacks:
            cb, route = self.async_callbacks.pop()
            cb(*route())

            frontik_testing_logger.debug('Callback executed, {0} left'.format(len(self.async_callbacks)))


Get = namedtuple('Get', ('url', 'data'))
Post = namedtuple('Post', ('url', 'data'))

class FrontikAppRequestMocker(object):

    PageMethodsMapping = {
        Get: ('get_page', frontik.util.make_get_request),
        Post: ('post_page', frontik.util.make_post_request)
    }

    def serve_request(self, request, handler):
        module_name = 'pages.' + '.'.join(request.url.strip('/').split('/'))
        module = frontik_import(module_name)
        method_name, request_factory = self.PageMethodsMapping.get(request.__class__, self.PageMethodsMapping[Get])
        http_request = request_factory(request.url, request.data)

        try:
            handler.call(module.Page.__dict__[method_name], handler)
            response = HTTPResponseWrapper(http_request, code=200, headers={'Content-Type': 'application/xml'})
            response.body = handler.xml.doc.to_string()
            return response
        except HTTPError, e:
            code = e.status_code
            if code not in httplib.responses:
                code = 500
            return HTTPResponseWrapper(http_request, code=code, headers=e.headers, exception=e)
        except Exception, e:
            return HTTPResponseWrapper(http_request, code=500, exception=e)


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
