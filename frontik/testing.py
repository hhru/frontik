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
from tornado_mock.httpclient import patch_http_client, set_stub
from yarl import URL

from frontik.app import FrontikApplication
from frontik.loggers import bootstrap_core_logging
from frontik.media_types import APPLICATION_JSON, APPLICATION_PROTOBUF, APPLICATION_XML, TEXT_PLAIN
from frontik.options import options
from frontik.server import bind_socket, run_server
from frontik.util import make_url, safe_template

import multiprocessing
from ctypes import c_bool, c_int
from frontik.process import WorkerState


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

        init_workers_count_down = multiprocessing.Value(c_int, options.workers)
        master_done = multiprocessing.Value(c_bool, False)
        count_down_lock = multiprocessing.Lock()
        worker_state = WorkerState(init_workers_count_down, master_done, count_down_lock)  # type: ignore
        frontik_app.worker_state = worker_state
        await frontik_app.init()

        async def _server_coro() -> None:
            await run_server(frontik_app, sock)

        server_task = asyncio.create_task(_server_coro())
        yield
        server_task.cancel()
        await asyncio.wait_for(frontik_app.http_client.client_session.close(), timeout=5)

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
        self.http_client: AIOHttpClientWrapper = frontik_app.http_client
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
