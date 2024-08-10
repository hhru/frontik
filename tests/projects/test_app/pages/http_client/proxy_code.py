from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/http_client/proxy_code', cls=PageHandler)
async def get_page(handler: PageHandler = get_current_handler()):
    result = await handler.get_url('http://127.0.0.1:' + handler.get_query_argument('port'), '')
    handler.finish(str(result.status_code))
