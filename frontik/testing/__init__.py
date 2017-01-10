# coding=utf-8

import json
import logging
import os

from lxml import etree
from tornado.escape import to_unicode, utf8
from tornado.httpclient import AsyncHTTPClient, HTTPResponse
from tornado.httputil import HTTPHeaders
from tornado.testing import AsyncHTTPTestCase

from frontik.compat import basestring_type, iteritems, PY3, urlparse
from frontik.testing.service_mock import application_mock, raw_route, route as to_route, ServiceMock
from frontik.util import make_url

if PY3:
    from io import StringIO
else:
    from cStringIO import StringIO

logger = logging.getLogger('frontik.testing')


def get_response_stub(request, **kwargs):
    code = kwargs.pop('code', 200)
    buffer = kwargs.pop('buffer', None)
    buffer = StringIO(buffer) if isinstance(buffer, basestring_type) else buffer
    kwargs.setdefault('request_time', 1)

    return HTTPResponse(request, code, buffer=buffer, **kwargs)


def format_fail_safe(filename, format_string, **kwargs):
    if not kwargs:
        return format_string

    try:
        return format_string.format(**kwargs)
    except (KeyError, ValueError):
        logger.warning('Missing template key in {}, skipping processing'.format(filename))
        return format_string


def _guess_headers(fileName):
    if fileName.endswith('.json'):
        return HTTPHeaders({'Content-Type': 'json'})
    if fileName.endswith('.xml'):
        return HTTPHeaders({'Content-Type': 'xml'})
    return HTTPHeaders()


class FrontikTestCase(AsyncHTTPTestCase):
    def setUp(self):
        self.common_headers = {}
        super(FrontikTestCase, self).setUp()

    def get_http_client(self):
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
        return json.loads(to_unicode(self.fetch(path, query, **kwargs).body))

    def get_stub(self, path):
        return self._app.http_client.get_stub(path)

    def set_stub(self, service_route_tuple, response_file=None, response_function=None,
                 response_code=200, raw_response='', headers=None,
                 content_processor=format_fail_safe, **kwargs):
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
        service, route = service_route_tuple
        route = format_route(route, **kwargs)

        if response_function is not None:
            expect(service, route, response_function)
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
            headers=headers, buffer=content, effective_url=route.path, request_time=1.0
        )

        expect(service, route, response)

    def format_route(route, **kwargs):
        if isinstance(route, raw_route):
            path = format_fail_safe(route.path, route.path, **kwargs)
            query = format_fail_safe(route.query, route.query, **kwargs)
            return raw_route(path, query, *route[2:])

        return to_route(format_fail_safe(route, route, **kwargs))

    def expect(service_name, route, mock):
        service = http_client.routes.setdefault(service_name, ServiceMock({}))
        service.routes[route] = mock

    http_client.fetch_impl = fetch_impl
    http_client.get_stub = get_stub
    http_client.set_stub = set_stub

    return http_client
