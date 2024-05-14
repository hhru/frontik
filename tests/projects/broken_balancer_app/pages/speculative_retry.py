import asyncio

from fastapi import HTTPException

from frontik.handler import PageHandler
from frontik.routing import router


@router.put('/speculative_retry', cls=PageHandler)
async def put_page():
    await asyncio.sleep(0.8)
    raise HTTPException(503, 'broken, retry')
