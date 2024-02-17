import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        result = await self.get_url('http://127.0.0.1:' + self.get_argument('port'), '', request_timeout=0.1)

        if result.response.error:
            self.finish(str(result.response.error.code))
        else:
            self.finish(str(result.response.code))
