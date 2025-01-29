import asyncio
import typing
from typing import Awaitable, Optional, Union

from tornado import httputil

from frontik.handler_asgi import serve_tornado_request
from frontik.server_tasks import _server_tasks
from frontik.tornado_request import FrontikTornadoServerRequest

if typing.TYPE_CHECKING:
    from frontik.app import FrontikApplication


class TornadoConnectionHandler(httputil.HTTPMessageDelegate):
    def __init__(
        self,
        frontik_app: 'FrontikApplication',
        request_conn: httputil.HTTPConnection,
    ) -> None:
        self.connection = request_conn
        self.frontik_app = frontik_app
        self.request = None  # type: Optional[FrontikTornadoServerRequest]

    def headers_received(
        self,
        start_line: Union[httputil.RequestStartLine, httputil.ResponseStartLine],
        headers: httputil.HTTPHeaders,
    ) -> None:
        self.request = FrontikTornadoServerRequest(
            connection=self.connection,
            start_line=typing.cast(httputil.RequestStartLine, start_line),
            headers=headers,
        )
        self.process_request()

    def process_request(self) -> None:
        self._process_request()

    def _process_request(self) -> Optional[Awaitable[None]]:
        assert self.request is not None
        task = asyncio.create_task(serve_tornado_request(self.frontik_app, self.request))
        _server_tasks.add(task)
        task.add_done_callback(_server_tasks.discard)
        return task

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        assert self.request is not None
        task = asyncio.create_task(self.request.body_chunks.put(chunk))
        return task

    def finish(self) -> None:
        assert self.request is not None
        self.request.finished = True

    def on_connection_close(self) -> None:
        assert self.request is not None
        self.request.finished = True


class LegacyTornadoConnectionHandler(TornadoConnectionHandler):
    """Used because of
    1. Debug (requires request.body)
    2. FrontikPageHandler (full of legacy shit)
    """

    def process_request(self) -> None: ...

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        assert self.request is not None
        self.request.body += chunk
        return super().data_received(chunk)

    def finish(self) -> None:
        assert self.request is not None
        self.request._parse_body()
        super().finish()
        self._process_request()
