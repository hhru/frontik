from frontik import handler, media_types
from frontik.handler import router


class Page(handler.PageHandler):
    @router.get()
    async def get_page(self):
        result = await self.post_url(self.request.host, self.request.path)
        self.text = result.data

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'post_url success'
