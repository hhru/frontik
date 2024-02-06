import asyncio

import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.post()
    async def post_page(self):
        await asyncio.sleep(2)

        self.text = 'result'
