from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        self.text = '404'
        self.set_status(404)
