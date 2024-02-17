from frontik.handler import PageHandler, router


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        self.text = '404'
        self.set_status(404)
