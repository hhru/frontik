from tornado.web import HTTPError

from frontik.handler import PageHandler, router


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        await self.post_url(self.request.host, self.request.path, fail_fast=True)

    def get_page_fail_fast(self, failed_future):
        raise HTTPError(401)

    @router.post()
    async def post_page(self):
        raise HTTPError(403)
