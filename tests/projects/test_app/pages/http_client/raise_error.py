import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        await self.post_url(self.request.host, '/a-вот')

    def send_error(self, status_code=500, exc_info=None, **kwargs):
        if isinstance(exc_info[1], UnicodeEncodeError):
            self.finish('UnicodeEncodeError')
