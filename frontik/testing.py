import asyncio
import json
import logging
import re
from collections.abc import Callable
from typing import Any

import pytest
from aioresponses import aioresponses
from http_client import AIOHttpClientWrapper
from http_client.request_response import RequestBuilder, RequestResult
from lxml import etree
from tornado.escape import utf8
from tornado.httpserver import HTTPServer
from tornado.log import app_log
from tornado.testing import AsyncHTTPTestCase, bind_unused_port
from tornado_mock.httpclient import patch_http_client, set_stub
from yarl import URL

from frontik.app import FrontikApplication

# noinspection PyUnresolvedReferences
from frontik.loggers import bootstrap_logger
from frontik.media_types import APPLICATION_JSON, APPLICATION_PROTOBUF, APPLICATION_XML, TEXT_PLAIN
from frontik.options import options
from frontik.util import make_url, safe_template


class FrontikTestCase(AsyncHTTPTestCase):
    """Deprecated, use FrontikTestBase instead"""

    def __init__(self, *args, **kwargs):
        self._app: FrontikApplication = None  # type: ignore
        super().__init__(*args, **kwargs)

    def get_http_client(self):
        """Overrides `AsyncHTTPTestCase.get_http_client` to separate unit test HTTPClient
        from application HTTPClient.

        This allows mocking HTTP requests made by application in unit tests.
        """
        self.forced_client = AIOHttpClientWrapper()
        return self.forced_client

    def fetch(self, path: str, query: dict | None = None, **kwargs: Any) -> RequestResult:  # type: ignore
        """Extends `AsyncHTTPTestCase.fetch` method with `query` kwarg.
        This argument accepts a `dict` of request query parameters that will be encoded
        and added to request path.
        Any additional kwargs will be passed to `AsyncHTTPTestCase.fetch`.
        """
        query = {} if query is None else query
        return super().fetch(make_url(path, **query), **kwargs)

    def fetch_xml(self, path: str, query: dict | None = None, **kwargs: Any) -> etree.Element:
        """Fetch the request and parse xml document from response body."""
        return etree.fromstring(utf8(self.fetch(path, query, **kwargs).raw_body))

    def fetch_json(self, path: str, query: dict | None = None, **kwargs: Any) -> Any:
        """Fetch the request and parse JSON tree from response body."""
        return json.loads(self.fetch(path, query, **kwargs).raw_body)

    def patch_app_http_client(self, app: FrontikApplication) -> None:
        """Patches application HTTPClient to enable requests stubbing."""
        patch_http_client(app.tornado_http_client)  # type: ignore

    def set_stub(
        self,
        url: str,
        request_method: str = 'GET',
        response_function: Callable | None = None,
        response_file: str | None = None,
        response_body: Any = '',
        response_code: int = 200,
        response_headers: Any = None,
        response_body_processor: Callable = safe_template,
        **kwargs: Any,
    ) -> None:
        set_stub(
            self._app.tornado_http_client,
            url,
            request_method,
            response_function,
            response_file,
            response_body,
            response_code,
            response_headers,
            response_body_processor,
            **kwargs,
        )

    def tearDown(self) -> None:
        if self._app.tornado_http_client is not None:
            self.io_loop.run_sync(self._app.tornado_http_client.client_session.close)
        if self.forced_client is not None:
            self.io_loop.run_sync(self.forced_client.client_session.close)
        super().tearDown()

    def configure_app(self, **kwargs: Any) -> None:
        """Updates or adds options to application config."""
        for name, val in kwargs.items():
            setattr(self._app.config, name, val)


class FrontikTestBase:
    @pytest.fixture(scope='session')
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        loop.close()

    @pytest.fixture(scope='class', autouse=True)
    def _enable_consul(self):
        options.consul_enabled = False

    @pytest.fixture(scope='class', autouse=True)
    async def inited_test_app(self, test_app, _enable_consul):
        await test_app.init()
        return test_app

    @pytest.fixture(scope='class', autouse=True)
    async def test_server_port(self, test_app):
        sock, port = bind_unused_port()
        http_server = HTTPServer(test_app)
        http_server.add_sockets([sock])

        options.stderr_log = True
        bootstrap_logger(app_log.name, logging.INFO)

        yield port

        http_server.stop()
        await asyncio.wait_for(http_server.close_all_connections(), timeout=5)

    @pytest.fixture(scope='class', autouse=True)
    async def app_client(self):
        http_client = AIOHttpClientWrapper()
        yield http_client
        await asyncio.wait_for(http_client.client_session.close(), timeout=5)

    @pytest.fixture(autouse=True)
    def _setup_client_server(
        self,
        inited_test_app: FrontikApplication,
        test_server_port: int,
        app_client: AIOHttpClientWrapper,
    ) -> None:
        self.app = inited_test_app
        self.port = test_server_port
        self.http_client = app_client

    @pytest.fixture(autouse=True)
    def setup_mock_client(self):
        with aioresponses(passthrough=['http://127.0.0.1']) as mock_client:
            self.mock_client = mock_client
            yield self.mock_client

    async def fetch(
        self,
        path: str,
        query: dict | None = None,
        method: str = 'GET',
        request_timeout: float = 2,
        **kwargs: Any,
    ) -> RequestResult:
        query = {} if query is None else query
        path = make_url(path, **query)
        host = f'http://127.0.0.1:{self.port}'

        request = RequestBuilder(
            host,
            'test',
            path,
            'test_request',
            method=method,
            request_timeout=request_timeout,
            **kwargs,
        )
        return await self.http_client.fetch(request)

    async def fetch_xml(
        self,
        path: str,
        query: dict | None = None,
        method: str = 'GET',
        **kwargs: Any,
    ) -> etree.Element:
        resp = await self.fetch(path, query, method, **kwargs)
        return etree.fromstring(utf8(resp.raw_body))

    async def fetch_json(self, path: str, query: dict | None = None, method: str = 'GET', **kwargs: Any) -> Any:
        resp = await self.fetch(path, query, method, **kwargs)
        return json.loads(resp.raw_body)

    def set_stub(
        self,
        url: URL | str | re.Pattern,
        request_method: str = 'GET',
        response_file: str | None = None,
        response_body: Any = '',
        response_code: int = 200,
        response_headers: dict | None = None,
        response_body_processor: Callable | None = safe_template,
        repeat: bool = True,
        **kwargs: Any,
    ) -> None:
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

        self.mock_client.add(
            url,
            method=request_method,
            status=response_code,
            headers=headers,
            body=content,
            repeat=repeat,
        )

    def configure_app(self, **kwargs: Any) -> None:
        for name, val in kwargs.items():
            setattr(self.app.config, name, val)

    @staticmethod
    def guess_content_type_headers(file_name: str) -> dict[str, str]:
        if file_name.endswith('.json'):
            return {'Content-Type': APPLICATION_JSON}
        if file_name.endswith('.xml'):
            return {'Content-Type': APPLICATION_XML}
        if file_name.endswith('.txt'):
            return {'Content-Type': TEXT_PLAIN}
        if file_name.endswith('.proto'):
            return {'Content-Type': APPLICATION_PROTOBUF}
        return {}
