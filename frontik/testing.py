# coding=utf-8

import logging
import os
from collections import namedtuple
from functools import partial

from lxml import etree
from tornado.escape import json_decode, utf8
from tornado.httpclient import AsyncHTTPClient, HTTPResponse
from tornado.httputil import HTTPHeaders
from tornado.testing import AsyncHTTPTestCase

# noinspection PyUnresolvedReferences
import frontik.options
from frontik.compat import basestring_type, iteritems, PY3, unquote_plus, urlparse
from frontik.util import make_url

if PY3:
    from io import StringIO
else:
    from cStringIO import StringIO

logger = logging.getLogger('frontik.testing')


def format_fail_safe(filename, format_string, **kwargs):
    if not kwargs:
        return format_string

    try:
        return format_string.format(**kwargs)
    except (KeyError, ValueError):
        logger.warning('Missing template key in {}, skipping processing'.format(filename))
        return format_string


class FrontikTestCase(AsyncHTTPTestCase):
    """Extends `tornado.testing.AsyncHTTPTestCase` with a possibility to mock application HTTP client calls."""

    def setUp(self):
        self.common_headers = {}
        super(FrontikTestCase, self).setUp()

    def get_http_client(self):
        AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient', max_clients=10)
        return AsyncHTTPClient(io_loop=self.io_loop, force_instance=True)

    def add_common_headers(self, headers):
        self.common_headers.update(headers)
        return self

    def fetch(self, path, query=None, **kwargs):
        headers = kwargs.get('headers')
        if headers is None:
            headers = {}

        headers.update(self.common_headers)
        kwargs['headers'] = headers

        query = {} if query is None else query
        return super(FrontikTestCase, self).fetch(make_url(path, **query), **kwargs)

    def fetch_xml(self, path, query=None, **kwargs):
        return etree.fromstring(utf8(self.fetch(path, query, **kwargs).body))

    def fetch_json(self, path, query=None, **kwargs):
        return json_decode(self.fetch(path, query, **kwargs).body)

    def get_stub(self, path):
        if not hasattr(self._app.http_client, 'get_stub'):
            raise NotImplementedError(
                'Application HTTP client does not support stubs — use frontik.testing.patch_http_client '
                'to add this support.'
            )

        return self._app.http_client.get_stub(path)

    def set_stub(self, service_route_tuple, response_file=None, response_function=None,
                 response_code=200, raw_response='', headers=None,
                 content_processor=format_fail_safe, **kwargs):
        if not hasattr(self._app.http_client, 'set_stub'):
            raise NotImplementedError(
                'Application HTTP client does not support stubs — use frontik.testing.patch_http_client '
                'to add this support.'
            )

        return self._app.http_client.set_stub(
            service_route_tuple, response_file, response_function, response_code, raw_response, headers,
            content_processor, **kwargs
        )

    def configure_app(self, **kwargs):
        for name, val in iteritems(kwargs):
            setattr(self._app.config, name, val)

        return self


def patch_http_client(http_client, stubs_path):
    http_client.routes = {}

    def fetch_impl(request, callback):
        def _fetch_mock():
            stub_name = urlparse.urlparse(request.url).netloc
            service_stub = http_client.routes.get(stub_name)

            if service_stub is None:
                raise NotImplementedError(
                    'Service stub "{}" is not found (services=[{}])'.format(request.url, ', '.join(http_client.routes))
                )

            callback(service_stub.fetch_request(request))

        http_client.io_loop.add_callback(_fetch_mock)

    def get_stub(path):
        with open(os.path.join(stubs_path, path)) as f:
            return f.read()

    def set_stub(service_route_tuple, response_file=None, response_function=None,
                 response_code=200, raw_response='', headers=None,
                 content_processor=format_fail_safe, **kwargs):
        service, route_url = service_route_tuple
        route_url = format_route(route_url, **kwargs)

        if response_function is not None:
            expect(service, route_url, response_function)
            return

        if response_file is not None:
            headers = _guess_headers(response_file)
            content = content_processor(response_file, get_stub(response_file), **kwargs)
        else:
            headers = HTTPHeaders({} if headers is None else headers)
            content = raw_response

        content = StringIO(content) if isinstance(content, basestring_type) else content

        response = HTTPResponse(
            None, response_code,
            headers=headers, buffer=content, effective_url=route_url.path, request_time=1.0
        )

        expect(service, route_url, response)

    def format_route(route_url, **kwargs):
        if isinstance(route_url, raw_route):
            path = format_fail_safe(route_url.path, route_url.path, **kwargs)
            query = format_fail_safe(route_url.query, route_url.query, **kwargs)
            return raw_route(path, query, *route_url[2:])

        return route(format_fail_safe(route_url, route_url, **kwargs))

    def expect(service_name, route_url, mock):
        service = http_client.routes.setdefault(service_name, ServiceMock({}))
        service.routes[route_url] = mock

    http_client.fetch_impl = fetch_impl
    http_client.get_stub = get_stub
    http_client.set_stub = set_stub

    return http_client


def get_response_stub(request, **kwargs):
    code = kwargs.pop('code', 200)
    buffer = kwargs.pop('buffer', None)
    buffer = StringIO(buffer) if isinstance(buffer, basestring_type) else buffer
    kwargs.setdefault('request_time', 1)

    return HTTPResponse(request, code, buffer=buffer, **kwargs)


def _guess_headers(fileName):
    if fileName.endswith('.json'):
        return HTTPHeaders({'Content-Type': 'json'})
    if fileName.endswith('.xml'):
        return HTTPHeaders({'Content-Type': 'xml'})
    return HTTPHeaders()


raw_route = namedtuple('raw_route', 'path query cookies method')


def route(url, cookies='', method='GET'):
    parsed_url = urlparse.urlparse(url)
    return raw_route(parsed_url.path, parsed_url.query, cookies, method)


def routes_match(a, b):
    if a.method != b.method:
        return False

    if a.path.strip('/') != b.path.strip('/'):
        return False

    a_qs, b_qs = map(partial(urlparse.parse_qs, keep_blank_values=True), (a.query, b.query))
    for param, a_value in iteritems(a_qs):
        if param not in b_qs or b_qs[param] != a_value:
            return False

    return True


class ServiceMock(object):
    def __init__(self, routes):
        self.routes = routes

    def fetch_request(self, req):
        route_of_incoming_request = route(req.url, method=req.method)
        for r in self.routes:
            destination_route = r if isinstance(r, raw_route) else route(r)
            if routes_match(destination_route, route_of_incoming_request):
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

        return get_response_stub(request, buffer=body, code=code, effective_url=request.url,
                                 headers=HTTPHeaders({'Content-Type': 'xml'}))
