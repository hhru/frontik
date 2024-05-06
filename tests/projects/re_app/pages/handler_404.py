from frontik.handler import PageHandler, get_current_handler
from frontik.routing import regex_router


@regex_router.get('/id/(?P<id1>[^/]+)/(?P<id2>[^/]+)', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.text = '404'
    handler.set_status(404)
