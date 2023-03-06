import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.post_url(self.request.host, '/a-вот')

    def send_error(self, status_code=500, exc_info=None, **kwargs):
        if isinstance(exc_info[1], UnicodeEncodeError):
            self.finish('UnicodeEncodeError')
