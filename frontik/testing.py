from collections import defaultdict, namedtuple
from functools import partial
import httplib
import logging
import re
from urlparse import urlparse
from tornado.ioloop import IOLoop
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

class ResponseStub(GeneralStub):
    def __init__(self, **kwargs):
        self.error = None
        self.body = None
        self.headers = {}
        super(ResponseStub, self).__init__(**kwargs)

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
        self.__fetch_url(url, data, callback, **kwargs)

    def post_url(self, url, data=None, callback=None, **kwargs):
        self.__fetch_url(url, data, callback, **kwargs)

    def put_url(self, url, data=None, callback=None, **kwargs):
        self.__fetch_url(url, data, callback, **kwargs)

    def delete_url(self, url, data=None, callback=None, **kwargs):
        self.__fetch_url(url, data, callback, **kwargs)

    def __fetch_url(self, url, data=None, callback=None, **kwargs):
        if data is None:
            data = {}

        route_url = urlparse(url).path
        for route_name, regex, route in self.routes:
            match = re.match(r'.+{0}/?$'.format(regex), route_url)
            if match:
                frontik_testing_logger.debug('Call to {url} will be mocked'.format(url=url))
                self.__add_callback(callback, route_name,
                    partial(route, url, data, **dict(match.groupdict(), **self.routes_data[route_name])))
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

    PageMethodNames = {
        Get: 'get_page',
        Post: 'post_page'
    }

    def serve_request(self, http_request, handler):
        module_name = 'pages.' + '.'.join(http_request.url.strip('/').split('/'))
        module = frontik_import(module_name)

        try:
            page_method_name = self.PageMethodNames.get(http_request.__class__, self.PageMethodNames[Get])
            handler.call(module.Page.__dict__[page_method_name], handler)
            return ResponseStub(code=200, body=handler.xml.doc.to_string(), headers={'Content-Type': 'application/xml'})
        except HTTPError, e:
            code = e.status_code
            if code not in httplib.responses:
                code = 500
            return ResponseStub(code=code, headers=e.headers, exception=e)
        except Exception, e:
            return ResponseStub(code=500, exception=e)


def service_response(response_type):
    def __wrapper(func):
        def __internal(url, data, *args, **kwargs):
            result = func(url, data, *args, **kwargs)
            if isinstance(result, tuple):
                response_body, response = result
            else:
                response_body = result
                response = ResponseStub(code=200)

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
