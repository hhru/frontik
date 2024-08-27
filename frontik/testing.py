import asyncio
import json
import re
from collections.abc import Callable
from typing import Any, Optional, Union

import pytest
from aioresponses import aioresponses
from http_client import AIOHttpClientWrapper
from http_client.request_response import RequestBuilder, RequestResult
from lxml import etree
from tornado.escape import utf8
from tornado.httpserver import HTTPServer
from tornado.testing import AsyncHTTPTestCase
from tornado_mock.httpclient import patch_http_client, set_stub
from yarl import URL

from frontik.app import FrontikApplication
from frontik.loggers import bootstrap_core_logging
from frontik.media_types import APPLICATION_JSON, APPLICATION_PROTOBUF, APPLICATION_XML, TEXT_PLAIN
from frontik.options import options
from frontik.util import bind_socket, make_url, safe_template


class FrontikTestBase:
    @pytest.fixture(scope='session')
    def event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        loop.close()

    @pytest.fixture(scope='class', autouse=True)
    async def _run_server(self, frontik_app):
        options.stderr_log = True
        options.consul_enabled = False
        bootstrap_core_logging(options.log_level, options.log_json, options.suppressed_loggers)

        sock = bind_socket(options.host, 0)
        options.port = sock.getsockname()[1]

        await frontik_app.init()

        http_server = HTTPServer(frontik_app)
        http_server.add_sockets([sock])

        yield

        http_server.stop()
        await asyncio.wait_for(http_server.close_all_connections(), timeout=5)

    @pytest.fixture(scope='class')
    def with_tornado_mocks(self):
        return False

    @pytest.fixture(autouse=True)
    async def _finish_server_setup(
        self,
        frontik_app: FrontikApplication,
        _run_server: None,
        with_tornado_mocks: bool,
    ) -> None:
        self.app = frontik_app
        self.port = options.port
        self.http_client: AIOHttpClientWrapper = frontik_app.http_client_factory.http_client
        self.use_tornado_mocks = with_tornado_mocks
        if with_tornado_mocks:
            patch_http_client(self.http_client, fail_on_unknown=False)

    @pytest.fixture(autouse=True)
    def setup_mock_client(self, passthrow_hosts):
        with aioresponses(passthrough=passthrow_hosts) as mock_client:
            self.mock_client = mock_client
            yield self.mock_client

    @pytest.fixture()
    def passthrow_hosts(self):
        return ['http://127.0.0.1', 'http://localhost']

    def get_http_port(self) -> int:
        return self.port

    async def fetch(
        self,
        path: str,
        query: Optional[dict] = None,
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
        query: Optional[dict] = None,
        method: str = 'GET',
        **kwargs: Any,
    ) -> etree.Element:
        resp = await self.fetch(path, query, method, **kwargs)
        return etree.fromstring(utf8(resp.raw_body))

    async def fetch_json(self, path: str, query: Optional[dict] = None, method: str = 'GET', **kwargs: Any) -> Any:
        resp = await self.fetch(path, query, method, **kwargs)
        return json.loads(resp.raw_body)

    def set_stub(
        self,
        url: str,
        request_method: str = 'GET',
        response_function: Optional[Callable] = None,
        response_file: Optional[str] = None,
        response_body: Any = '',
        response_code: int = 200,
        response_headers: Any = None,
        response_body_processor: Callable = safe_template,
        repeat: bool = True,
        **kwargs: Any,
    ) -> None:
        _set_stub = self.set_stub_old if self.use_tornado_mocks else self.set_stub_new
        _set_stub(  # type: ignore
            url,
            request_method,
            response_function,
            response_file,
            response_body,
            response_code,
            response_headers,
            response_body_processor,
            repeat,
            **kwargs,
        )

    def set_stub_old(
        self,
        url: str,
        request_method: str = 'GET',
        response_function: Optional[Callable] = None,
        response_file: Optional[str] = None,
        response_body: Any = '',
        response_code: int = 200,
        response_headers: Any = None,
        response_body_processor: Callable = safe_template,
        repeat: bool = True,
        **kwargs: Any,
    ) -> None:
        set_stub(
            self.http_client,
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

    def set_stub_new(
        self,
        url: Union[URL, str, re.Pattern],
        request_method: str = 'GET',
        response_function: None = None,
        response_file: Optional[str] = None,
        response_body: Any = '',
        response_code: int = 200,
        response_headers: Optional[dict] = None,
        response_body_processor: Callable = safe_template,
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


class FrontikTestCase(AsyncHTTPTestCase):
    """Deprecated, use FrontikTestBase instead"""

    def __init__(self, *args, **kwargs):
        self._app: FrontikApplication  # type: ignore
        super().__init__(*args, **kwargs)

    def get_http_client(self):
        """Overrides `AsyncHTTPTestCase.get_http_client` to separate unit test HTTPClient
        from application HTTPClient.

        This allows mocking HTTP requests made by application in unit tests.
        """
        self.forced_client = AIOHttpClientWrapper()
        return self.forced_client

    def fetch(self, path: str, query: Optional[dict] = None, **kwargs: Any) -> RequestResult:  # type: ignore
        """Extends `AsyncHTTPTestCase.fetch` method with `query` kwarg.
        This argument accepts a `dict` of request query parameters that will be encoded
        and added to request path.
        Any additional kwargs will be passed to `AsyncHTTPTestCase.fetch`.
        """
        query = {} if query is None else query
        return super().fetch(make_url(path, **query), **kwargs)

    def fetch_xml(self, path: str, query: Optional[dict] = None, **kwargs: Any) -> etree.Element:
        """Fetch the request and parse xml document from response body."""
        return etree.fromstring(utf8(self.fetch(path, query, **kwargs).raw_body))

    def fetch_json(self, path: str, query: Optional[dict] = None, **kwargs: Any) -> Any:
        """Fetch the request and parse JSON tree from response body."""
        return json.loads(self.fetch(path, query, **kwargs).raw_body)

    def patch_app_http_client(self, _app: FrontikApplication) -> None:
        """Patches application HTTPClient to enable requests stubbing."""
        patch_http_client(self.http_client)

    def set_stub(
        self,
        url: str,
        request_method: str = 'GET',
        response_function: Optional[Callable] = None,
        response_file: Optional[str] = None,
        response_body: Any = '',
        response_code: int = 200,
        response_headers: Any = None,
        response_body_processor: Callable = safe_template,
        **kwargs: Any,
    ) -> None:
        set_stub(
            self.http_client,
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
        if self.http_client is not None:
            self.io_loop.run_sync(self.http_client.client_session.close)  # type: ignore
        if self.forced_client is not None:
            self.io_loop.run_sync(self.forced_client.client_session.close)
        super().tearDown()

    def configure_app(self, **kwargs: Any) -> None:
        """Updates or adds options to application config."""
        for name, val in kwargs.items():
            setattr(self._app.config, name, val)
