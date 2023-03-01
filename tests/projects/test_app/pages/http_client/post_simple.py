from frontik import handler, media_types


class Page(handler.PageHandler):
    async def get_page(self):
        result = await self.post_url(self.request.host, self.request.path)
        self.text = result.data

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'post_url success'
