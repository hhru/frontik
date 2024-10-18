from tornado.web import HTTPError

from frontik.routing import router


@router.put('/retry_error')
async def put_page():
    raise HTTPError(503, 'broken, retry')
