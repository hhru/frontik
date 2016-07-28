# coding=utf-8

""" Frontik app testing helpers.
See source code for get_doc_shows_what_expected for example that doubles as test
"""

from collections import namedtuple
from functools import partial
import json
from logging import getLogger
import sys

from lxml import etree
from tornado.escape import to_unicode
from tornado.httpclient import HTTPResponse
import tornado.httpserver
from tornado.httputil import HTTPHeaders
from tornado.ioloop import IOLoop
import tornado.options
from tornado.util import raise_exc_info
import tornado.web

import frontik.app
from frontik.compat import basestring_type, iteritems, PY3, unquote_plus, urlparse
import frontik.handler
import frontik.handler_active_limit
import frontik.http_client
import frontik.loggers
import frontik.options

if PY3:
    from io import StringIO
else:
    from cStringIO import StringIO

tornado.options.options.stderr_log = True
tornado.options.options.loglevel = 'debug'
frontik.loggers.bootstrap_core_logging()


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
        self.no_keep_alive = True

    def write(self, chunk, callback=None):
        pass

    def finish(self):
        pass

    def set_close_callback(self, callback):
        pass


raw_route = namedtuple('raw_route', 'path query cookies method')


def route(url, cookies='', method='GET'):
    parsed_url = urlparse.urlparse(url)
    return raw_route(parsed_url.path, parsed_url.query, cookies, method)


def route_less_or_equal_than(a, b):
    # ignore cookies and headers for now
    return a.method == b.method and url_less_or_equal_than(a, b)


def url_less_or_equal_than(a, b):
    if a.path.strip('/') != b.path.strip('/'):
        return False
    return query_less_than_or_equal(a.query, b.query)


def query_less_than_or_equal(a, b):
    a, b = map(partial(urlparse.parse_qs, keep_blank_values=True), (a, b))
    for i in a:
        bi = b.get(i)
        if bi is None or bi != a[i]:
            return False
    return True


class ServiceMock(object):
    def __init__(self, routes):
        self.routes = routes

    def fetch_request(self, req):
        route_of_incoming_request = route(req.url, method=req.method)
        for r in self.routes:
            destination_route = r if isinstance(r, raw_route) else route(r)
            if route_less_or_equal_than(destination_route, route_of_incoming_request):
                result = self.get_result(req, self.routes[r])
                result.request = req
                return result

        raise NotImplementedError(
            "No route in service mock matches request '{0} {1}', tried to match following:\n'{2}'".format(
                req.method, unquote_plus(req.url), "';\n'".join([unquote_plus(str(r)) for r in self.routes])
            )
        )

    def get_result(self, request, handler):
        if callable(handler):
            return self.get_result(request, handler(request))
        elif isinstance(handler, basestring_type):
            code, body = 200, handler
        elif isinstance(handler, tuple):
            try:
                code, body = handler
            except ValueError:
                raise ValueError(
                    'Could not unpack {0!s} to (code, body) tuple that is a result to request {1} {2!s}'.format(
                        handler, unquote_plus(request.url), request)
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


def application_mock(handlers, config):
    class Mock(frontik.app.FrontikApplication):
        def application_urls(self):
            return handlers

        def application_config(self):
            return config

    return Mock


class EmptyEnvironment(object):

    class LocalHandlerConfig(object):
        pass

    def __init__(self, **application_kwargs):
        self.log = getLogger('service_mock')
        self._config = EmptyEnvironment.LocalHandlerConfig()

        self._request = tornado.httpserver.HTTPRequest('GET', '/', remote_ip='127.0.0.1')
        self._request.connection = DummyConnection()

        self._registry = {}
        self._response_text = None

        self.application_kwargs = application_kwargs
        for (key, value) in iteritems(application_kwargs):
            setattr(self, key, value)

    def expect(self, **kwargs):
        for name, routes in iteritems(kwargs):
            service = self._registry.setdefault(name, ServiceMock({}))
            service.routes.update(routes)
            setattr(self._config, name, 'http://' + name + '/')

        return self

    def route_request(self, request):
        service = self._get_candidate_service(request.url)
        if service:
            return service.fetch_request(request)
        else:
            return False

    def _get_candidate_service(self, url):
        return self._registry[urlparse.urlparse(url).netloc]

    def configure(self, **kwargs):
        for name, val in iteritems(kwargs):
            setattr(self._config, name, val)
        return self

    def add_headers(self, headers):
        self._request.headers.update(headers)
        return self

    def add_arguments(self, arguments):
        for key, val in iteritems(arguments):
            self._request.arguments[key] = [val] if isinstance(val, basestring_type) else val
        return self

    def get_arguments(self, name):
        return self._request.arguments.get(name, [])

    def add_request_body(self, body):
        self._request.body = body
        return self

    def call_get(self, page_handler, raise_exceptions=True):
        self._request.method = 'GET'
        return self._call_function(page_handler, raise_exceptions)

    def call_post(self, page_handler, raise_exceptions=True):
        self._request.method = 'POST'
        return self._call_function(page_handler, raise_exceptions)

    def call_put(self, page_handler, raise_exceptions=True):
        self._request.method = 'PUT'
        return self._call_function(page_handler, raise_exceptions)

    def call_delete(self, page_handler, raise_exceptions=True):
        self._request.method = 'DELETE'
        return self._call_function(page_handler, raise_exceptions)

    def _call_function(self, handler_class, raise_exceptions=True):
        # Create application with the only route — handler_class
        application = application_mock([('', handler_class)], self._config)(**{
            'app': 'frontik.testing',
        })

        for (key, value) in iteritems(self.application_kwargs):
            setattr(application, key, value)

        # Mock methods

        def fetch(request, callback, **kwargs):
            IOLoop.instance().add_callback(partial(self._fetch_mock, request, callback, **kwargs))

        application.curl_http_client.fetch = fetch

        # raise_exceptions kwarg is deprecated
        if raise_exceptions:
            exceptions = []
            old_handle_request_exception = handler_class._handle_request_exception

            def handle_request_exception(handler, e):
                old_handle_request_exception(handler, e)
                exceptions.append(sys.exc_info())

            handler_class._handle_request_exception = handle_request_exception

        old_flush = handler_class.flush

        def flush(handler, *args, **kwargs):
            self._response_text = b''.join(handler._write_buffer)
            old_flush(handler, *args, **kwargs)
            IOLoop.instance().add_callback(IOLoop.instance().stop)

        handler_class.flush = flush

        self._handler = application(self._request)
        IOLoop.instance().start()

        if raise_exceptions and exceptions:
            raise_exc_info(exceptions[0])

        return TestResult(self._config, self._request, self._handler, self._response_text)

    def _fetch_mock(self, request, callback, **kwargs):
        self.log.debug('trying to route ' + request.url)

        try:
            result = self.route_request(request)
        except NotImplementedError as e:
            self.log.error('request to missing service')
            raise e

        callback(result)


class TestResult(object):
    def __init__(self, config, request, handler, response_text):
        self._config = config
        self._request = request
        self._handler = handler
        self._response_text = response_text

    def get_xml_response(self):
        return etree.fromstring(self._response_text)

    def get_json_response(self):
        return json.loads(self.get_text_response())

    def get_text_response(self):
        return to_unicode(self._response_text)

    def get_headers(self):
        return self._handler._headers

    def get_status(self):
        return self._handler.get_status()
