import asyncio

from fastapi import HTTPException

from frontik.routing import router


@router.post('/speculative_no_retry')
async def post_page():
    await asyncio.sleep(0.8)
    raise HTTPException(500, 'broken')
