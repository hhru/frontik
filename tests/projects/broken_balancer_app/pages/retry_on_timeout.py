import asyncio

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.delete('/retry_on_timeout', cls=PageHandler)
async def delete_page(handler=get_current_handler()):
    await asyncio.sleep(2)

    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'
