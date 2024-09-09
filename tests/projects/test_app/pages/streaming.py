from typing import AsyncIterable

from fastapi.responses import StreamingResponse

from frontik.media_types import TEXT_PLAIN
from frontik.routing import plain_router as router


@router.get('/stream')
async def get_page():
    async def iterable() -> AsyncIterable:
        yield b'response+'
        yield b'second_part'

    return StreamingResponse(content=iterable(), headers={'Content-type': TEXT_PLAIN})
