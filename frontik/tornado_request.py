import asyncio
from typing import Optional

from tornado import httputil

EOF = object()


class FrontikTornadoServerRequest(httputil.HTTPServerRequest):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)
        self.body_chunks: asyncio.Queue = asyncio.Queue(maxsize=100000)
        self.request_id = None
        self.finished = False
        self.canceled = False
        self.handler_name: Optional[str] = None
