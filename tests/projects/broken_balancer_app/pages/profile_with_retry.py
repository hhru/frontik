from tornado.web import HTTPError

from frontik.routing import router


@router.put('/profile_with_retry')
async def put_page():
    raise HTTPError(503, 'broken')
