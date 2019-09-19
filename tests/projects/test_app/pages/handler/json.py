from tornado.web import HTTPError
import frontik.handler


class Page(frontik.handler.PageHandler):
    def _page_handler(self):
        if self.json_request is None:
            raise HTTPError(400)
        self.text = self.json_request.get('foo', 'baz')

    def post_page(self):
        return self._page_handler()

    def put_page(self):
        return self._page_handler()
