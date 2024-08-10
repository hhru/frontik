import asyncio

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.post('/no_retry_timeout', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    await asyncio.sleep(2)

    handler.text = 'result'
