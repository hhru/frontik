from tornado.web import HTTPError

from frontik.handler import PageHandler
from frontik.routing import plain_router


@plain_router.post('/retry_connect', cls=PageHandler)
async def post_page():
    raise HTTPError(503, 'broken, retry')
