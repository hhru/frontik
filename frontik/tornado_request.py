import asyncio

from tornado import httputil


class FrontikTornadoServerRequest(httputil.HTTPServerRequest):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)
        self.body_chunks: asyncio.Queue = asyncio.Queue(maxsize=100000)
        self.request_id = None
        self.finished = False
