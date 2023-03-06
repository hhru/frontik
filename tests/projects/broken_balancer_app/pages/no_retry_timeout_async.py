import asyncio

import frontik.handler


class Page(frontik.handler.PageHandler):
    async def post_page(self):
        await asyncio.sleep(2)

        self.text = 'result'
