import asyncio

from tornado.web import HTTPError

from frontik import handler


class Page(handler.PageHandler):
    async def put_page(self):
        await asyncio.sleep(0.8)
        raise HTTPError(503, 'broken, retry')
