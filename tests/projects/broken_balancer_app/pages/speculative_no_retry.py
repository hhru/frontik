import asyncio

from tornado.web import HTTPError

from frontik import handler


class Page(handler.AwaitablePageHandler):
    async def post_page(self):
        await asyncio.sleep(0.8)
        raise HTTPError(500, 'broken')
