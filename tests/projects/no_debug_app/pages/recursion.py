from frontik import handler, media_types
from frontik.handler import router


class Page(handler.PageHandler):
    @router.get()
    async def get_page(self):
        n = int(self.get_argument('n'))
        if n > 0:
            result = await self.get_url(self.request.host, self.request.path + f'?n={n - 1}')
            self.set_header('Content-Type', media_types.TEXT_PLAIN)
            if result.failed:
                self.text = str(result.status_code)
            else:
                self.text = f'200 {result.data}'
