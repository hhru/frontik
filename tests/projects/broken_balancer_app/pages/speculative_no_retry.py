import asyncio

from fastapi import HTTPException

from frontik.handler import PageHandler
from frontik.routing import router


@router.post('/speculative_no_retry', cls=PageHandler)
async def post_page():
    await asyncio.sleep(0.8)
    raise HTTPException(500, 'broken')
