from frontik.handler import HTTPErrorWithPostprocessors, PageHandler, router
from frontik.util import gather_list


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        async def bad_post_requests() -> None:
            results = await gather_list(
                self.post_url(self.request.host, self.request.path),
                self.post_url(self.request.host, self.request.path),
                self.post_url(self.request.host, self.request.path),
                self.post_url(self.request.host, self.request.path),
            )
            for _ in results:
                raise AssertionError()

        self.run_task(bad_post_requests())

        self.text = 'This is just a plain text'
        raise HTTPErrorWithPostprocessors(403)
