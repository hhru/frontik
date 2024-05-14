import asyncio

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/http_client/fibonacci', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    n = int(handler.get_query_argument('n'))

    handler.set_header('Content-Type', media_types.TEXT_PLAIN)

    if n < 2:
        handler.text = '1'
        return

    handler.acc = 0

    r1, r2 = await asyncio.gather(
        handler.get_url(handler.get_header('host'), handler.path, data={'n': str(n - 1)}),
        handler.get_url(handler.get_header('host'), handler.path, data={'n': str(n - 2)}),
    )
    handler.acc += int(r1.data)
    handler.acc += int(r2.data)
    handler.text = str(handler.acc)
