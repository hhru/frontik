from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/http_client/post_simple', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    result = await handler.post_url(handler.get_header('host'), handler.path)
    handler.text = result.data


@router.post('/http_client/post_simple', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'post_url success'
