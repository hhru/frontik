import asyncio
import json
import logging
from collections.abc import Callable, Generator
from typing import Any, Optional

import pytest
from http_client import AIOHttpClientWrapper
from http_client.request_response import RequestBuilder, RequestResult
from http_client.testing import MockHttpClient
from lxml import etree
from tornado.escape import utf8
from tornado.httpserver import HTTPServer

from frontik.app import FrontikApplication
from frontik.media_types import APPLICATION_JSON, APPLICATION_PROTOBUF, APPLICATION_XML, TEXT_PLAIN
from frontik.options import options
from frontik.util import bind_socket, make_url, safe_template

log = logging.getLogger('server')


class FrontikTestBase:
    @pytest.fixture(scope='class', autouse=True)
    async def _bind_socket(self):
        sock = bind_socket(options.host, 0)
        options.port = sock.getsockname()[1]
        yield sock
        sock.close()

    @pytest.fixture(scope='class', autouse=True)
    async def _run_app(self, frontik_app, _bind_socket):
        options.consul_enabled = False

        await frontik_app.init()
        with frontik_app.worker_state.count_down_lock:
            frontik_app.worker_state.init_workers_count_down.value -= 1

        http_server = HTTPServer(frontik_app, xheaders=options.xheaders, max_body_size=options.max_body_size)
        http_server.add_sockets([_bind_socket])
        log.info('Successfully inited application %s', frontik_app.app_name)

        yield

        http_server.stop()
        await asyncio.wait_for(http_server.close_all_connections(), timeout=5)

    @pytest.fixture(autouse=True)
    async def _setup_app_links(self, frontik_app: FrontikApplication, _run_app: None) -> None:
        self.app = frontik_app
        self.port = options.port

    @pytest.fixture(autouse=True)
    def setup_mock_http_client(
        self, frontik_app: FrontikApplication, passthrow_hosts: list[str]
    ) -> Generator[MockHttpClient]:
        self.http_client: AIOHttpClientWrapper = frontik_app.http_client.http_client_impl
        with MockHttpClient(passthrough=passthrow_hosts) as mock_http_client:
            self.mock_http_client = mock_http_client
            yield self.mock_http_client

    @pytest.fixture
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
        """
        Url and request_method are related to mocked resource
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

        self.mock_http_client.add(
            url,
            method=request_method,
            status=response_code,
            headers=headers,
            body=content,
            repeat=repeat,
            response_function=response_function,
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
