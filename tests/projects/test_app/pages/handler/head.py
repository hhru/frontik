import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        self.set_header('X-Foo', 'Bar')
        self.text = 'response body must be empty for HEAD requests'
