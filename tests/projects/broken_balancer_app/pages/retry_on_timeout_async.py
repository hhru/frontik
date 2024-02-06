import asyncio

from frontik import handler, media_types
from frontik.handler import router


class Page(handler.PageHandler):
    @router.delete()
    async def delete_page(self):
        await asyncio.sleep(2)

        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
