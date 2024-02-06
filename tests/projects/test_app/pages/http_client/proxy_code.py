import frontik.handler
from frontik.handler import router

class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        result = await self.get_url('http://127.0.0.1:' + self.get_argument('port'), '')
        self.finish(str(result.status_code))
