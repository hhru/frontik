from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/recursion', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    n = int(handler.get_query_argument('n'))
    if n > 0:
        result = await handler.get_url(handler.get_header('host'), handler.path + f'?n={n - 1}')
        handler.set_header('Content-Type', media_types.TEXT_PLAIN)
        if result.failed:
            handler.text = str(result.status_code)
        else:
            handler.text = f'200 {result.data}'
