import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):

        def callback(element, response):
            self.finish(str(response.code))

        self.get_url('http://127.0.0.1:' + self.get_argument('port'), '', callback=callback)
