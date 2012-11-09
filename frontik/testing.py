from collections import defaultdict, namedtuple
import httplib
import logging
import re
from urlparse import urlparse
from lxml import etree
import sys
from tornado.ioloop import IOLoop

from frontik.doc import Doc
from frontik.handler import HTTPError


frontik_testing_logger = logging.getLogger('frontik_testing')
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

class AsyncGroup(object):
    def __init__(self, finish_cb, name=None, **kwargs):
        self.counter = 0
        self.finished = False
        self.finish_cb = finish_cb
        self.log_fun = frontik_testing_logger.debug
        self.name = name

        if self.name is not None:
            self.log_name = '{0} group'.format(self.name)
        else:
            self.log_name = 'group'

    def log(self, msg):
        self.log_fun(self.log_name + ": " + msg)

    def finish(self):
        if not self.finished:
            self.log('finishing')
            self.finished = True

            try:
                self.finish_cb()
            finally:
                # prevent possible cycle references
                self.finish_cb = None

    def try_finish(self):
        self.log('trying to finish')
        if self.counter == 0:
            self.finish()

    def _inc(self):
        self.counter += 1

    def _dec(self):
        self.counter -= 1

    def add(self, intermediate_cb):
        self._inc()
        self.log('adding callback')

        def new_cb(*args, **kwargs):
            if not self.finished:
                try:
                    self._dec()
                    self.log('executing callback')
                    intermediate_cb(*args, **kwargs)
                finally:
                    pass
            else:
                self.log('ignoring response because of already finished group')

        return new_cb

    def add_notification(self):
        self._inc()
        self.log('adding notification')

        def new_cb(*args, **kwargs):
            self._dec()
            self.log('executing notification')
            self.try_finish()

        return new_cb

# Replace AsyncGroup and IOLoop instance

import frontik.async
frontik.async.AsyncGroup = AsyncGroup

IOLoop._instance = GeneralStub(
    add_callback=lambda x: x()
)

class HandlerMock(GeneralStub):

    def __init__(self, routes, config, **kwargs):
        super(HandlerMock, self).__init__(**kwargs)
        self.log = frontik_testing_logger
        self.routes = routes
        self.routes_data = defaultdict(dict)
        self.routes_called = defaultdict(int)
        self.config = config
        self.xml = GeneralStub(doc=Doc(root_node = etree.Element('doc', frontik = 'true')))
        self.finish_group = AsyncGroup(lambda: None)

        if getattr(self, 'cookies', None) is None:
            self.cookies = {}

        if getattr(self, 'request_id', None) is None:
            self.request_id = 'TEST_REQUEST_ID'

        self.request = GeneralStub(
            arguments=kwargs.get('arguments', {}),
            headers=kwargs.get('headers', {}),
            host=kwargs.get('host', '')
        )

    def set_route_data(self, route_name, **kwargs):
        self.routes_data[route_name].update(kwargs)

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
                frontik_testing_logger.debug('Call to {url} is mocked'.format(url=url))
                self.routes_called[route_name] += 1
                callback(*route(url, data, fetch_url_args=kwargs, **dict(match.groupdict(), **self.routes_data[route_name])))
                return

        raise NotImplementedError('Url "{url}" is not mocked'.format(url=route_url))

    def called_once(self, route):
        return self.get_call_count(route) == 1

    def not_called(self, route):
        return self.get_call_count(route) == 0

    def get_call_count(self, route):
        return self.routes_called[route]


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
            module.Page.__dict__[page_method_name](handler)
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
