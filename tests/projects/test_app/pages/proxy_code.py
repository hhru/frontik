from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/proxy_code', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    result = await handler.get_url('http://127.0.0.1:' + handler.get_query_argument('port'), '', request_timeout=0.1)

    if result.response.error:
        handler.finish(str(result.response.error.code))
    else:
        handler.finish(str(result.response.code))
