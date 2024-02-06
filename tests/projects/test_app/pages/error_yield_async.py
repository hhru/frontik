import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        await self.post_url(self.request.host, self.request.path)
        return 1 / 0

    @router.post()
    async def post_page(self):
        self.text = 'result'
