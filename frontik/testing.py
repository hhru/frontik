import json
import logging
import re

from aioresponses import aioresponses
from http_client import AIOHttpClientWrapper
from http_client.request_response import RequestBuilder, RequestResult
from lxml import etree
import pytest
import pytest_asyncio
from tornado.escape import utf8
from tornado.httpserver import HTTPServer
from tornado.log import app_log
from tornado.testing import AsyncHTTPTestCase, bind_unused_port
from tornado_mock.httpclient import patch_http_client, set_stub
from yarl import URL

from frontik.app import FrontikApplication
# noinspection PyUnresolvedReferences
from frontik.loggers import bootstrap_logger
from frontik.media_types import APPLICATION_JSON, APPLICATION_XML, APPLICATION_PROTOBUF, TEXT_PLAIN
from frontik.options import options
from frontik.util import make_url, safe_template

from tornado.testing import bind_unused_port
from tornado.httpserver import HTTPServer
import pytest_asyncio
from http_client.request_response import RequestBuilder, RequestResult
from tornado.httputil import HTTPServerRequest, HTTPHeaders, HTTPConnection
from asyncio import Future
from typing import Optional


class FrontikTestCase(AsyncHTTPTestCase):
    """Deprecated, use FrontikTestBase instead"""

    def get_http_client(self):
        """Overrides `AsyncHTTPTestCase.get_http_client` to separate unit test HTTPClient
        from application HTTPClient.

        This allows mocking HTTP requests made by application in unit tests.
        """
        self.forced_client = AIOHttpClientWrapper()
        return self.forced_client

    def fetch(self, path, query=None, **kwargs) -> RequestResult:
        """Extends `AsyncHTTPTestCase.fetch` method with `query` kwarg.
        This argument accepts a `dict` of request query parameters that will be encoded
        and added to request path.
        Any additional kwargs will be passed to `AsyncHTTPTestCase.fetch`.
        """
        query = {} if query is None else query
        return super().fetch(make_url(path, **query), **kwargs)

    def fetch_xml(self, path, query=None, **kwargs):
        """Fetch the request and parse xml document from response body."""
        return etree.fromstring(utf8(self.fetch(path, query, **kwargs).raw_body))

    def fetch_json(self, path, query=None, **kwargs):
        """Fetch the request and parse JSON tree from response body."""
        return json.loads(self.fetch(path, query, **kwargs).raw_body)

    def patch_app_http_client(self, app):
        """Patches application HTTPClient to enable requests stubbing."""
        patch_http_client(app.tornado_http_client)

    def set_stub(self, url, request_method='GET',
                 response_function=None, response_file=None, response_body='',
                 response_code=200, response_headers=None,
                 response_body_processor=safe_template, **kwargs):

        set_stub(
            self._app.tornado_http_client, url, request_method,
            response_function, response_file, response_body, response_code, response_headers,
            response_body_processor, **kwargs
        )

    def tearDown(self) -> None:
        if self._app.tornado_http_client is not None:
            self.io_loop.run_sync(
                self._app.tornado_http_client.client_session.close
            )
        if self.forced_client is not None:
            self.io_loop.run_sync(
                self.forced_client.client_session.close
            )
        super().tearDown()

    def configure_app(self, **kwargs):
        """Updates or adds options to application config."""
        for name, val in kwargs.items():
            setattr(self._app.config, name, val)

        return self


class FetchResult:
    def __init__(self, status, headers, body, reason):
        self.status_code = status
        self.headers = headers
        self.raw_body = body
        self.reason = reason


class TestHTTPConnection(HTTPConnection):
    def set_close_callback(self, *args):
        pass

    def finish(self):
        pass

    def write(self, chunk: bytes):
        future = Future()
        future.set_result(None)
        return future

    def write_headers(self, start_line, headers: HTTPHeaders, chunk: Optional[bytes] = None):
        self.handler_result = FetchResult(start_line.code, headers, chunk, start_line.reason)


class FrontikTestBase:
    @pytest.fixture(scope="function", autouse=True)
    def setup_mock_client(self, mock_client):
        self.mock_client: MockClient = mock_client

    @pytest_asyncio.fixture(scope='function', autouse=True)
    async def wrap_test_method(self):
        """
        code before and after yield point are similar to setUp and tearDown methods
        """
        self._app = self.create_app()
        await self._app.init()
        self.http_client = AIOHttpClientWrapper()

        sock, port = bind_unused_port()
        self._port = port
        self._http_server = HTTPServer(self._app)
        self._http_server.add_sockets([sock])

        options.stderr_log = True
        bootstrap_logger(app_log.name, logging.INFO)

        yield

        self._http_server.stop()
        await self._http_server.close_all_connections()
        await self.http_client.client_session.close()

    def create_app(self) -> FrontikApplication:
        raise NotImplementedError()

    def get_app(self) -> FrontikApplication:
        return self._app

    def get_http_port(self) -> int:
        return self._port

    async def fetch(self, path: str, query=None, method: str = 'GET', **kwargs) -> RequestResult:
        headers = kwargs.get('headers')
        if headers is None:
            headers = {}

        query = {} if query is None else query
        path = make_url(path, **query)

        """
        monkey patch for tornado.web._HandlerDelegate.execute
        """
        conn = TestHTTPConnection()
        request = HTTPServerRequest(method=method, uri=path, headers=headers, body=None, connection=conn)
        delegate = self.get_app().find_handler(request)
        delegate.handler = delegate.handler_class(
            delegate.application, delegate.request, **delegate.handler_kwargs
        )
        transforms = [t(delegate.request) for t in delegate.application.transforms]

        await delegate.handler._execute(transforms, *delegate.path_args, **delegate.path_kwargs)
        await delegate.handler.response_written_future

        return conn.handler_result

    async def fetch_xml(self, path, query=None, **kwargs):
        resp = await self.fetch(path, query, **kwargs)
        return etree.fromstring(utf8(resp.raw_body))

    async def fetch_json(self, path, query=None, **kwargs):
        resp = await self.fetch(path, query, **kwargs)
        return json.loads(resp.raw_body)

    def set_stub(self, url: URL | str | re.Pattern, request_method='GET',
                 response_file=None, response_body='',
                 response_code=200, response_headers=None,
                 response_body_processor=safe_template, **kwargs):
        """
        url and request_method are related to mocked resource
        other params are related to mocked response
        """
        self.mock_client.mock(
            url, request_method=request_method,
            response_file=response_file, response_body=response_body,
            response_code=response_code, response_headers=response_headers,
            response_body_processor=response_body_processor,
            **kwargs
        )

    def configure_app(self, **kwargs):
        for name, val in kwargs.items():
            setattr(self.get_app().config, name, val)


class MockClient:
    def __init__(self, mock_client_impl):
        self.mock_client_impl: aioresponses = mock_client_impl

    def mock(self, url: URL | str | re.Pattern, request_method='GET',
             response_file=None, response_body='', response_code=200, response_headers=None,
             response_body_processor=safe_template, repeat=True, **kwargs):
        """
        url and request_method are related to mocked resource
        other params are related to mocked response
        """
        if isinstance(url, str):
            url = safe_template(url, **kwargs)

        if response_file is not None:
            headers = self.guess_content_type_headers(response_file)
            with open(response_file, 'rb') as f:
                content = f.read()
        else:
            headers = {}
            content = response_body

        if callable(response_body_processor):
            content = response_body_processor(content, **kwargs)

        if response_headers is not None:
            headers.update(response_headers)

        self.mock_client_impl.add(url, method=request_method,
                                  status=response_code, headers=headers, body=content, repeat=repeat)

    @staticmethod
    def guess_content_type_headers(file_name):
        if file_name.endswith('.json'):
            return {'Content-Type': APPLICATION_JSON}
        if file_name.endswith('.xml'):
            return {'Content-Type': APPLICATION_XML}
        if file_name.endswith('.txt'):
            return {'Content-Type': TEXT_PLAIN}
        if file_name.endswith('.proto'):
            return {'Content-Type': APPLICATION_PROTOBUF}
        return {}


@pytest.fixture
def mock_client():
    with aioresponses(passthrough=['http://127.0.0.1']) as m:
        yield MockClient(m)
