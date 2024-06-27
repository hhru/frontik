import asyncio

from tornado.web import HTTPError

from frontik.handler import PageHandler
from frontik.routing import router


@router.post('/speculative_no_retry', cls=PageHandler)
async def post_page():
    await asyncio.sleep(0.8)
    raise HTTPError(500, 'broken')
