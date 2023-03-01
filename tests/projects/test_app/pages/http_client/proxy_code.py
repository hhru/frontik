import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        result = await self.get_url('http://127.0.0.1:' + self.get_argument('port'), '')
        self.finish(str(result.response.code))
