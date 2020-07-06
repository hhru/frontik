from tornado.web import HTTPError

from frontik.handler import PageHandler, HTTPErrorWithPostprocessors


class Page(PageHandler):
    def get_page(self):
        self.json.put(self.post_url(self.request.host, self.request.path, fail_fast=True))

    def get_page_fail_fast(self, failed_future):
        self.json.put({'error': 'some_error'})
        raise HTTPErrorWithPostprocessors()

    def post_page(self):
        raise HTTPError(403)
