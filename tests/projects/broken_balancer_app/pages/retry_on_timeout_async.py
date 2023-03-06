import asyncio

from frontik import handler, media_types


class Page(handler.PageHandler):
    async def delete_page(self):
        await asyncio.sleep(2)

        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
