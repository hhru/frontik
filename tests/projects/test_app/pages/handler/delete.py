import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        result = await self.delete_url('http://' + self.request.host, self.request.path, data={'data': 'true'})
        if not result.failed:
            self.json.put(result.data)

    async def post_page(self):
        result = await self.delete_url('http://backend', self.request.path, fail_fast=True)
        if not result.failed:
            self.json.put(result.data)

    async def delete_page(self):
        self.json.put({'delete': self.get_argument('data')})
