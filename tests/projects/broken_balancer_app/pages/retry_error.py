from tornado.web import HTTPError

from frontik.handler import PageHandler
from frontik.routing import router


@router.put('/retry_error', cls=PageHandler)
async def put_page():
    raise HTTPError(503, 'broken, retry')
