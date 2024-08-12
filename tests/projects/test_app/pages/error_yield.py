from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/error_yield', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    await handler.post_url(handler.get_header('host'), handler.path)
    return 1 / 0


@plain_router.post('/error_yield', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.text = 'result'
