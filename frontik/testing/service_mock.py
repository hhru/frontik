# -*- coding: utf-8 -*-
''' Frontik app testing helpers. See source code for get_doc_shows_what_expected for example that doubles as test '''

from tornado.httpclient import HTTPResponse, HTTPClient
from cStringIO import StringIO
import tornado.httpserver
from tornado.httputil import HTTPHeaders
from tornado.ioloop import IOLoop
import functools
import tornado.web
from urlparse import urlparse, parse_qs
from collections import namedtuple
from tornado.httpclient import HTTPRequest
import frozen_dict

import sys
import os
import os.path
from os.path import dirname
from urllib import unquote_plus as unquote

import unittest

from logging import getLogger
import tornado.options
tornado.options.process_options_logging()


def EmptyEnvironment():
    return ExpectingHandler()

def expecting(*args, **kwargs):
    return ExpectingHandler().expect(*args, **kwargs)

def HTTPResponseStub(request=None, code=200, headers=None, buffer=None,
                    effective_url='stub', error=None, request_time=1,
                    time_info=None):
    ''' Helper HTTPResponse object with error-proof defaults '''
    if headers is None:
        headers = {}
    if time_info is None:
        time_info = {}
    return(HTTPResponse(request, code, headers, StringIO(buffer),
                effective_url, error, request_time,
                time_info))

def fromFile(fileName):
    '''fromFile(fileName) -> file contents from existing file. Will serch fileName recursively to support for different locations from wich to test from'''
    for root, _, _ in os.walk("."):
        path = os.path.join(root, fileName)
        if (os.path.exists(path)):
            with open(path) as f:
                return f.read()
    raise ValueError("fromFile: could not find + " + fileName + " while searching recursively from " + os.path.abspath("."))

raw_route = namedtuple('raw_route', 'path query cookies method headers')

def route(url, cookies = "", method = 'GET', headers = None):
    if headers is None:
        headers = {}
    parsed = urlparse(url)
    return _route(parsed.path, parsed.query, cookies, method, frozen_dict.FrozenDict(headers))

def _route (path, query = "", cookies = "", method = 'GET', headers = None):
    if headers is None:
        headers = {}
    return raw_route(path, query, cookies, method, frozen_dict.FrozenDict(headers))

#===

def route_less_or_equal_than(a,b):
    # ignore cookies and headers for now
    return a.method == b.method and url_less_or_equal_than(a,b)

def url_less_or_equal_than(a,b):
    if a.path.lstrip('/') != b.path.lstrip('/'):
        return False
    return query_less_than_or_equal(a.query, b.query)

def query_less_than_or_equal(a, b):
    a, b = map(parse_query, (a, b))
    for i in a:
        bi = b.get(i)
        if bi is None:
            return False
        if bi!= a[i]:
            return False
    return True

def parse_query(query):
    return dict([(k,tuple(v)) for k,v in parse_qs(query, keep_blank_values=True).iteritems()])

def to_route(req):
    return route(req.url, method = req.method, headers = req.headers)

class ServiceMock(object):
    def __init__(self, routes, strict = 0):
        self.routes = routes
        self.strict = strict

    def fetch_request(self, req):
        route_of_incoming_request = to_route(req)
        for r in self.routes:
            destination_route = r if isinstance(r, raw_route) else route(r)
            if route_less_or_equal_than(destination_route, route_of_incoming_request):
                result = self.get_result(req, self.routes[r])
                if self.strict:
                    del self.routes[r]
                return result
        raise NotImplementedError("No route in service mock matches request to " + unquote(req.url) +
                                    " tried to match following: '" +
                                    "'; '".join([unquote(str(rt)) for rt in self.routes]) +
                                    "', " +
                                    "strictness = " + str(self.strict))

    def get_result(self, request, handler):
        if callable(handler):
            return self.get_result(request, handler(request))
        elif isinstance(handler, basestring):
            (code, body) = (200, handler)
        elif isinstance(handler, tuple):
            try:
                (code, body) = handler
            except ValueError:
                raise ValueError("Could not unpack :" + str(handler) +
                        " to (code, body) tuple that is a result to request " + unquote(request.url) + " "
                        + str(request))
        elif isinstance(handler, HTTPResponse):
            return handler
        else: raise ValueError("Handler " + str(handler) + "\n that matched request " + request.url + " "
            + str(request) + "\n is neither tuple nor HTTPResponse nor basestring instance nor callable returning any of above.")
        return HTTPResponseStub(request, buffer = body, effective_url = request.url,
                headers = HTTPHeaders({'Content-Type': 'xml'}))

class ExpectingHandler(object):
    def __init__(self, **kwarg):
        self.log = getLogger('service_mock')
        # this import is side-effecty and is used to initialize tornado options
        import frontik.options
        assert frontik.options # silence code style checkers
        # prevent log clubbering
        tornado.options.options.warn_no_jobs = False

        # handler stuff
        from frontik.app import App
        relative_path_to_test_application = dirname(__file__)
        self.app = App("", relative_path_to_test_application,)
        self.app._initialize()

        self.request = tornado.httpserver.HTTPRequest('GET', '/', remote_ip = "remote_ip")
        del self.request.connection
        def finish(*arg, **kwarg):
            pass
        def write(s, callback=None):
            if callback:
                self._callback_heap.append((None, callback))

        IOLoop.instance().add_callback = lambda callback: self._callback_heap.append((None, callback))


        self.request.write = write
        self.request.finish = finish

        def async_callback(tornado_handler, callback, *args, **kwargs):
            if callback is None:
                return None
            if args or kwargs:
                callback = functools.partial(callback, *args, **kwargs)
            def wrapper(*args, **kwargs):
                try:
                    return callback(*args, **kwargs)
                except Exception, e:
                    self._exception_heap.append((sys.exc_type, sys.exc_value, sys.exc_traceback))
                    if tornado_handler._headers_written:
                        tornado_handler._logger.error("Exception after headers written",
                                      exc_info=True)
                    else:
                        tornado_handler._handle_request_exception(e)
            return wrapper

        tornado.web.RequestHandler.async_callback = async_callback
        tornado_handler = tornado.web.RequestHandler
        tornado_application = tornado.web.Application([(".*", tornado_handler)])

        self._handler = self.app(tornado_application, self.request, )
        self._handler.http_client = TestHttpClient(self)
        self._handler.get_error_html = lambda handler, exception : None

        def flush(include_footers=False, callback=None):
            if callback:
                self._callback_heap.append((None, callback))
        self._handler.flush = flush
        self._handler.finish = finish
        #init registry
        self.registry = {}

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
                request, callback = callbacks_snapshot.pop(0)
                if request:
                    self.log.debug('trying to route ' + request.url)
                    try:
                        result = self.route_request(request)
                    except NotImplementedError as e:
                        self.log.warn("Request to missing service")
                        raise e
                    callback(result)
                    self.raise_exceptions()
                else:
                    if callback:
                        callback()

    def call(self, method, *arg, **kwarg):
        if hasattr(method, 'im_class'):
            self._handler.__class__ = type('Page', (method.im_class,) + self._handler.__class__.__bases__, {})
        handler = self._handler
        handler.prepare()
        handler._finished = False
        handler.finished = False
        handler._headers_written = False
        self._callback_heap = []
        self._exception_heap = []
        result = method(handler, *arg, **kwarg)
        self.raise_exceptions()
        self.process_callbacks()

        self._result = result
        return self

    def get_handler(self,):
        return self._handler

    def get_result(self,):
        return self._result

    def get_doc(self, ):
        return self._handler.doc

    def process_fetch(self, req, callback):
        self._callback_heap.append((req, callback))

#===

class TestHttpClient(HTTPClient):
    '''_callback_heap aware'''
    def __init__(self, callback_heap):
        self._callback_heap = callback_heap

    def fetch(self, req, callback):
        self._callback_heap.process_fetch(req, callback)

class TestServiceMock(unittest.TestCase):
    def test_parse_query_ok(self, ):
        self.assertEquals(parse_query('a=&z=q&vacancyId=1432459'), {'a' : ('',), 'z' : ('q',), 'vacancyId' : ('1432459',)})
    def test_equal_route(self, ):
        self.assertTrue(route_less_or_equal_than(route("/abc/?q=1"), route("/abc/?q=1")), "equal routes do not match each other")
    def test_swapped(self, ):
        self.assertTrue(route_less_or_equal_than(route("/abc/?a=2&q=1"), route("/abc/?q=1&a=2")), "swapped query parameters do not match each other")
    def test_different_paths(self, ):
        self.assertFalse(route_less_or_equal_than(route("/abc?q=1"), route("/abc/?q=1")), "different paths should not match")
    def test_right_query_is_less(self, ):
        self.assertFalse(route_less_or_equal_than(route("/abc/?a=2&q=1"), route("/abc/?q=1")), "insufficient query parameters should not match")

    def test_routing_by_url(self, ):
        gogogo_handler = '<xml></xml>'
        routes = {'asdasd.ru' : {
                '/gogogo' : gogogo_handler
            } }
        expecting_handler = expecting( **routes )
        assert expecting_handler.route_request(HTTPRequest('http://asdasd.ru/gogogo')).body == gogogo_handler

    def test_get_doc_shows_what_expected(self, ):
        '''intergation test that shows main test path'''
        import lxml.etree
        from frontik.handler import HTTPError, AsyncGroup

        def function_under_test(handler, ):
            def finished():
                res = lxml.etree.Element("result")
                res.text = str(handler.result)
                handler.doc.put(res)
            handler.result = 0
            ag = AsyncGroup(finished)
            def accumulate(xml, response):
                if response.code >= 400:
                    raise HTTPError(503, "remote server returned error with code =" + str(response.code))
                if xml is None:
                    raise HTTPError(503)
                handler.result += int(xml.findtext("a"))

            handler.get_url(handler.config.serviceHost +  'vacancy/1234', callback = ag.add(accumulate))
            handler.get_url(handler.config.serviceHost + 'employer/1234', callback = ag.add(accumulate))

        class EtalonTest(unittest.TestCase):
            def runTest(self,):
                doc = expecting(serviceHost = {
                        '/vacancy/1234' : (200, '<b><a>1</a></b>'),
                        '/employer/1234' : '<b><a>2</a></b>'
                }).call(function_under_test).get_doc().root_node

                self.assertEqual(doc.findtext('result'), '3')

        #test that test works (does not throw exception)
        ts = unittest.TestSuite()
        ts.addTest(EtalonTest())
        tr = unittest.TextTestRunner()
        tr.run(ts)

if __name__ == '__main__':
    unittest.main()

