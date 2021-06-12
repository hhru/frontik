from tornado.web import HTTPError

from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        self.post_url(self.request.host, self.request.path, fail_fast=True)

    def get_page_fail_fast(self, failed_future):
        raise HTTPError(401)

    async def post_page(self):
        raise HTTPError(403)
