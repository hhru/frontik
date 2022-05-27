from frontik.handler import AwaitablePageHandler


class Page(AwaitablePageHandler):
    data = {}

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

    async def head_page(self):
        self._record_failed_request({'head_failed': True})

    async def post_page(self):
        self._record_failed_request({'post_failed': True})

    async def put_page(self):
        self._record_failed_request({'put_failed': True})

    async def delete_page(self):
        self._record_failed_request({'delete_failed': True})

    def _record_failed_request(self, data):
        Page.data.update(data)
        raise ValueError('Some error')
