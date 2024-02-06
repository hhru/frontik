from frontik.handler import PageHandler, router


class Page(PageHandler):
    data: dict = {}

    @router.get()
    async def get_page(self):
        if self.request.method == 'HEAD':
            await self.head_page()
            return

        if not self.data:
            # HTTP request with waited=False and fail_fast=True should not influence responses to client
            await self.head_url(self.request.host, self.request.path, waited=False, fail_fast=True)
            await self.post_url(self.request.host, self.request.path, waited=False, fail_fast=True)
            await self.put_url(self.request.host, self.request.path, waited=False, fail_fast=True)
            await self.delete_url(self.request.host, self.request.path, waited=False, fail_fast=True)

            self.json.put({'get': True})
        else:
            self.json.put(self.data)
            self.data = {}

    async def head_page(self) -> None:
        self._record_failed_request({'head_failed': True})

    @router.post()
    async def post_page(self):
        self._record_failed_request({'post_failed': True})

    @router.put()
    async def put_page(self):
        self._record_failed_request({'put_failed': True})

    @router.delete()
    async def delete_page(self):
        self._record_failed_request({'delete_failed': True})

    def _record_failed_request(self, data: dict) -> None:
        Page.data.update(data)
        msg = 'Some error'
        raise ValueError(msg)
