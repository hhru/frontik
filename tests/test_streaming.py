from typing import AsyncIterable

from fastapi.responses import StreamingResponse

from frontik.media_types import TEXT_PLAIN
from frontik.routing import router
from frontik.testing import FrontikTestBase


@router.get('/stream')
async def get_page():
    async def iterable() -> AsyncIterable:
        yield b'response+'
        yield b'second_part'

    return StreamingResponse(content=iterable(), headers={'Content-type': TEXT_PLAIN})


class TestStreaming(FrontikTestBase):
    async def test_streaming_response(self):
        response = await self.fetch('/stream')
        assert response.headers['content-type'] == 'text/plain'
        assert response.raw_body == b'response+second_part'
