import asyncio

from frontik.routing import router


@router.delete('/retry_on_timeout')
async def delete_page():
    await asyncio.sleep(2)

    return 'result'
