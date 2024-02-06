import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    def _page_handler(self) -> None:
        self.text = self.get_body_argument('foo', 'baz')

    @router.post()
    async def post_page(self):
        return self._page_handler()

    @router.put()
    async def put_page(self):
        return self._page_handler()
