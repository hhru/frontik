from collections import defaultdict, namedtuple
from functools import partial
import httplib
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
from frontik.handler import HTTPError

frontik_testing_logger = logging.getLogger('frontik.testing')
frontik_testing_logger.addHandler(logging.StreamHandler(strm=sys.stdout))

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

class PageHandlerWrapper(frontik.handler.PageHandler):

    def __init__(self, routes, handler_params, *args, **kwargs):
        super(PageHandlerWrapper, self).__init__(*args, **kwargs)
        self.log = frontik_testing_logger

        for name, value in handler_params.items():
            setattr(self, name, value)

        self.async_callbacks = []
        self.routes = routes
        self.routes_data = defaultdict(dict)
        self.routes_called = defaultdict(int)
        self.exceptions = []

    # Mock methods replacements

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
        self.prepare()
        function(*args, **kwargs)
        self.execute_callbacks()

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

    def execute_callbacks(self):
        while self.async_callbacks:
            cb, route = self.async_callbacks.pop()
            frontik_testing_logger.debug('Executing callback, {0} left'.format(len(self.async_callbacks)))

            try:
                cb(*route())
            except Exception, e:
                self.exceptions.append(e)
                frontik_testing_logger.debug('Callback raised exception: {0}'.format(e))

        while self.exceptions:
            raise self.exceptions.pop()

class Mock(object):
    def __init__(self, routes, config, **kwargs):
        self.routes = routes
        self.config = config
        self.handler_default_params = kwargs

    def new_handler(self, **kwargs):
        ph_globals = frontik.handler.PageHandlerGlobals(GeneralStub(
            config=self.config
        ))

        request = HTTPRequestWrapper('GET', '/', kwargs.get('arguments', {}), headers=kwargs.pop('headers', {}))
        handler_params = dict(self.handler_default_params, **kwargs)
        handler = PageHandlerWrapper(self.routes, handler_params, Application(), request, ph_globals)
        return handler

Get = namedtuple('Get', ('url', 'data'))
Post = namedtuple('Post', ('url', 'data'))

class FrontikAppRequestMocker(object):

    PageMethodsMapping = {
        Get: ('get_page', frontik.util.make_get_request),
        Post: ('post_page', frontik.util.make_post_request)
    }

    def serve_request(self, handler, request):
        method_name, request_factory = self.PageMethodsMapping.get(request.__class__, self.PageMethodsMapping[Get])
        http_client_request = request_factory(request.url, request.data)

        module_name = 'pages.' + '.'.join(request.url.strip('/').split('/'))
        module = frontik_import(module_name)

        try:
            handler.call(module.Page.__dict__[method_name], handler)
            response = HTTPResponseWrapper(http_client_request, code=200, headers={'Content-Type': 'application/xml'})
            response.body = handler.xml.doc.to_string()
            return response
        except HTTPError, e:
            code = e.status_code
            if code not in httplib.responses:
                code = 500
            return HTTPResponseWrapper(http_client_request, code=code, headers=e.headers)
        except Exception, e:
            return HTTPResponseWrapper(http_client_request, code=500)


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
