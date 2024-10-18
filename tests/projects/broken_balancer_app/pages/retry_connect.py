from tornado.web import HTTPError

from frontik.routing import router


@router.post('/retry_connect')
async def post_page():
    raise HTTPError(503, 'broken, retry')
