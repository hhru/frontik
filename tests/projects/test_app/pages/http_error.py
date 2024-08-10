from tornado.web import HTTPError

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/http_error', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    code = int(handler.get_query_argument('code', '200'))
    raise HTTPError(code)
