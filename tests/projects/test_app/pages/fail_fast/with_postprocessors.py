from tornado.web import HTTPError

from frontik.handler import HTTPErrorWithPostprocessors, PageHandler, router


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        result = await self.post_url(self.request.host, self.request.path, fail_fast=True)
        self.json.put(result.data)

    def get_page_fail_fast(self, failed_future):
        self.json.put({'error': 'some_error'})
        raise HTTPErrorWithPostprocessors()

    @router.post()
    async def post_page(self):
        raise HTTPError(403)
