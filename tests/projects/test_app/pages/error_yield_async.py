import frontik.handler


class Page(frontik.handler.AwaitablePageHandler):
    async def get_page(self):
        await self.post_url(self.request.host, self.request.path)
        return 1 / 0

    def post_page(self):
        self.text = 'result'
