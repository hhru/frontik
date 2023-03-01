import asyncio

from frontik.handler import AbortAsyncGroup, PageHandler


class Page(PageHandler):
    data = {}

    async def get_page(self):
        if not self.data:
            self.json.put({'get': True})
            asyncio.create_task(self.coro())
        else:
            while not all(x in self.data for x in ('put_made', 'post_made', 'delete_cancelled')):
                await asyncio.sleep(0.05)

            self.json.put(self.data)
            self.data = {}

    def finish(self, chunk=None):
        super(Page, self).finish(chunk)
        if self.request.method == 'GET':
            # HTTP requests with waited=False can be made after handler is finished
            self.json.put(self.put_url(self.request.host, self.request.path, waited=False))

    async def coro(self):
        result = await self.post_url(self.request.host, self.request.path, waited=False)
        self.json.put(result)

        # HTTP requests with waited=True are aborted after handler is finished
        try:
            await self.delete_url(self.request.host, self.request.path, waited=True)
        except AbortAsyncGroup:
            self.record_request({'delete_cancelled': True})

    async def post_page(self):
        self.record_request({'post_made': True})

    async def put_page(self):
        self.record_request({'put_made': True})

    async def delete_page(self):
        self.record_request({'delete_made': True})

    def record_request(self, data):
        self.json.put(data)
        Page.data.update(data)
