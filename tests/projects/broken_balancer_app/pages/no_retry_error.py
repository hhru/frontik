from tornado.web import HTTPError

from frontik.routing import router


@router.post('/no_retry_error')
async def post_page():
    raise HTTPError(500, 'something went wrong, no retry')
