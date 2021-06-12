import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.text = 'OK'
