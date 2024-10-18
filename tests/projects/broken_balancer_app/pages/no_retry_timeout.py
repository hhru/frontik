import asyncio

from frontik.routing import router


@router.post('/no_retry_timeout')
async def post_page():
    await asyncio.sleep(2)

    return 'result'
