import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        result = await self.delete_url('http://' + self.request.host, self.request.path, data={'data': 'true'})
        if not result.failed:
            self.json.put(result.data)

    @router.post()
    async def post_page(self):
        result = await self.delete_url('http://backend', self.request.path, fail_fast=True)
        if not result.failed:
            self.json.put(result.data)

    @router.delete()
    async def delete_page(self):
        self.json.put({'delete': self.get_argument('data')})
