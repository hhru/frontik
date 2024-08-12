from tornado.web import HTTPError

from frontik.handler import PageHandler
from frontik.routing import plain_router


@plain_router.put('/profile_without_retry', cls=PageHandler)
async def put_page():
    raise HTTPError(503, 'broken')
