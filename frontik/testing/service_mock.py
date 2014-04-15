# coding=utf-8

""" Frontik app testing helpers.
See source code for get_doc_shows_what_expected for example that doubles as test
"""

import frozen_dict
import traceback
import unittest
from collections import namedtuple
from cStringIO import StringIO
from logging import getLogger
from os.path import dirname
from urllib import unquote_plus as unquote
from urlparse import urlparse, parse_qs

import tornado.options
import tornado.web
from tornado.httpclient import HTTPResponse
from tornado.httputil import HTTPHeaders
from tornado.ioloop import IOLoop

import frontik.app
import frontik.handler
import tornado.httpserver
import frontik.options
import frontik.handler_active_limit

tornado.options.process_options_logging()


class HTTPResponseStub(HTTPResponse):
    def __init__(self, request=None, code=200, headers=None, buffer=None,
                 effective_url='stub', error=None, request_time=1,
                 time_info=None):

        headers = {} if headers is None else headers
        time_info = {} if time_info is None else time_info

        super(HTTPResponseStub, self).__init__(
            request, code, headers, StringIO(buffer), effective_url, error, request_time, time_info
        )


class DummyConnection(object):
    class DummyStream(object):
        def set_close_callback(self, callback):
            pass

    def __init__(self):
        self.stream = DummyConnection.DummyStream()

    def write(self, chunk):
        pass

    def finish(self):
        pass


raw_route = namedtuple('raw_route', 'path query cookies method headers')


def route(url, cookies="", method='GET', headers=None):
    if headers is None:
        headers = {}
    parsed = urlparse(url)
    return _route(parsed.path, parsed.query, cookies, method, frozen_dict.FrozenDict(headers))


def _route(path, query="", cookies="", method='GET', headers=None):
    if headers is None:
        headers = {}
    return raw_route(path, query, cookies, method, frozen_dict.FrozenDict(headers))


def route_less_or_equal_than(a, b):
    # ignore cookies and headers for now
    return a.method == b.method and url_less_or_equal_than(a, b)


def url_less_or_equal_than(a, b):
    if a.path.lstrip('/') != b.path.lstrip('/'):
        return False
    return query_less_than_or_equal(a.query, b.query)


def query_less_than_or_equal(a, b):
    a, b = map(parse_query, (a, b))
    for i in a:
        bi = b.get(i)
        if bi is None:
            return False
        if bi != a[i]:
            return False
    return True


def parse_query(query):
    return dict([(k, tuple(v)) for k, v in parse_qs(query, keep_blank_values=True).iteritems()])


def to_route(req):
    return route(req.url, method=req.method, headers=req.headers)


class ServiceMock(object):
    def __init__(self, routes, strict=0):
        self.routes = routes
        self.strict = strict

    def fetch_request(self, req):
        route_of_incoming_request = to_route(req)
        for r in self.routes:
            destination_route = r if isinstance(r, raw_route) else route(r)
            if route_less_or_equal_than(destination_route, route_of_incoming_request):
                result = self.get_result(req, self.routes[r])
                result.request = req
                if self.strict:
                    del self.routes[r]
                return result
        raise NotImplementedError(
            "No route in service mock matches request to: \n" +
            "{0} {1}\n tried to match following: \n'{2}', strictness = {3}".format(
                req.method,
                unquote(req.url),
                "';\n'".join([unquote(str(rt)) for rt in self.routes]),
                str(self.strict)))

    def get_result(self, request, handler):
        if callable(handler):
            return self.get_result(request, handler(request))
        elif isinstance(handler, basestring):
            (code, body) = (200, handler)
        elif isinstance(handler, tuple):
            try:
                (code, body) = handler
            except ValueError:
                raise ValueError(
                    'Could not unpack {0!s} to (code, body) tuple that is a result to request {1} {2!s}'.format(
                        handler, unquote(request.url), request)
                )
        elif isinstance(handler, HTTPResponse):
            return handler
        else:
            raise ValueError(
                'Handler {0!s}\n that matched request {1} {2!s}\n is neither tuple nor HTTPResponse '
                'nor basestring instance nor callable returning any of above.'.format(handler, request.url, request)
            )
        return HTTPResponseStub(request, buffer=body, code=code, effective_url=request.url,
                                headers=HTTPHeaders({'Content-Type': 'xml'}))


class EmptyEnvironment(object):

    class LocalHandlerConfig(object):
        pass

    def __init__(self, **kwarg):
        self.log = getLogger('service_mock')

        frontik_app = frontik.app.App('', dirname(__file__))
        tornado_app = frontik.app.get_app([('', frontik_app)])

        frontik_app.app_globals.config = EmptyEnvironment.LocalHandlerConfig()
        frontik_app.app_globals.http_client.fetch = self.process_fetch
        IOLoop.instance().add_callback = lambda callback: self._callback_heap.append((None, callback, None))

        self.request = tornado.httpserver.HTTPRequest('GET', '/', remote_ip='127.0.0.1')
        self.request.connection = DummyConnection()

        self.registry = {}
        self._handler = tornado_app(self.request)

    def expect(self, **kwargs):
        for name, routes in kwargs.iteritems():
            service = self.registry.setdefault(name, ServiceMock({}))
            service.routes.update(routes)
            setattr(self._handler.config, name, 'http://' + name + '/')

        return self

    def do(self, handler_processor):
        handler_processor(self._handler)
        return self

    def get_candidate_service(self, url):
        return self.registry[urlparse(url).netloc]

    def route_request(self, request):
        url = request.url
        service = self.get_candidate_service(url)
        if service:
            return service.fetch_request(request)
        else:
            return False

    def configure(self, **kwargs):
        config = self._handler.config
        for name in kwargs:
            setattr(config, name, kwargs[name])
        return self

    def add_headers(self, headers):
        self._handler.request.headers.update(headers)
        return self

    def add_arguments(self, arguments):
        for key, val in arguments.iteritems():
            self._handler.request.arguments[key] = [val] if isinstance(val, basestring) else val
        return self

    def raise_exceptions(self):
        if self._exception_heap:
            raise self._exception_heap[0][0], self._exception_heap[0][1], self._exception_heap[0][2]

    def process_callbacks(self):
        while self._callback_heap:
            callbacks_snapshot = self._callback_heap
            self._callback_heap = []
            while callbacks_snapshot:
                request, callback, tb = callbacks_snapshot.pop(0)
                if request:
                    self.log.debug('trying to route ' + request.url)
                    try:
                        result = self.route_request(request)
                    except NotImplementedError as e:
                        self.log.warn("Request to missing service")
                        if tb:
                            self.log.info("Caller stack trace might help:\n" + ''.join(traceback.format_list(tb)))
                        raise e
                    callback(result)
                    self.raise_exceptions()
                else:
                    if callback:
                        callback()

    def call_with_exception_handler(self, method, *args, **kwargs):
        try:
            self.call(method, *args, **kwargs)
        except Exception as e:
            self._handler._handle_request_exception(e)

        return self

    def call(self, method, *args, **kwargs):
        if hasattr(method, 'im_class'):
            self._handler.__class__ = type('Page', (method.im_class,) + self._handler.__class__.__bases__, {})

        self._callback_heap = []
        self._exception_heap = []

        self._handler.prepare()
        self._handler._finished = False
        self._handler._headers_written = False

        self._result = method(self._handler, *args, **kwargs)
        self.raise_exceptions()
        self.process_callbacks()

        frontik.handler_active_limit.PageHandlerActiveLimit.working_handlers_count = 0

        return self

    def get_handler(self,):
        return self._handler

    def get_result(self,):
        return self._result

    def get_doc(self, ):
        return self._handler.doc

    def get_json(self, ):
        return self._handler.json

    def process_fetch(self, req, callback, **kwargs):
        tb = traceback.extract_stack()
        while tb and not tb.pop()[2] == 'fetch_request':
            pass
        self._callback_heap.append((req, callback, tb))


if __name__ == '__main__':
    unittest.main()
