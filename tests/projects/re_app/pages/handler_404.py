from frontik.handler import AwaitablePageHandler


class Page(AwaitablePageHandler):
    async def get_page(self):
        self.text = '404'
        self.set_status(404)
