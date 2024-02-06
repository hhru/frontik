import asyncio

from tornado.web import HTTPError

from frontik import handler
from frontik.handler import router


class Page(handler.PageHandler):
    @router.post()
    async def post_page(self):
        await asyncio.sleep(0.8)
        raise HTTPError(500, 'broken')
