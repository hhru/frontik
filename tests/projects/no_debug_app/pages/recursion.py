from frontik import handler, media_types


class Page(handler.PageHandler):
    async def get_page(self):
        n = int(self.get_argument('n'))
        if n > 0:
            result = await self.get_url(
                self.request.host, self.request.path + f'?n={n - 1}',
            )
            self.set_header('Content-Type', media_types.TEXT_PLAIN)
            if result.response.error:
                self.text = str(result.response.code)
            else:
                self.text = f'200 {result.data}'
