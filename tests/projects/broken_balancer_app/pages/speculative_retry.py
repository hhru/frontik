import asyncio

from tornado.web import HTTPError

from frontik import handler
from frontik.handler import router


class Page(handler.PageHandler):
    @router.put()
    async def put_page(self):
        await asyncio.sleep(0.8)
        raise HTTPError(503, 'broken, retry')
