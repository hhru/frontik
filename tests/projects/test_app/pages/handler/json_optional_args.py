import frontik.handler


class Page(frontik.handler.PageHandler):
    def _page_handler(self) -> None:
        self.text = self.get_body_argument('foo', 'baz')

    async def post_page(self):
        return self._page_handler()

    async def put_page(self):
        return self._page_handler()
