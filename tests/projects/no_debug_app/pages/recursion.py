from tornado.escape import to_unicode

from frontik import handler, media_types


class Page(handler.PageHandler):
    async def get_page(self):
        def _cb(text, response):
            self.set_header('Content-Type', media_types.TEXT_PLAIN)
            if response.error:
                self.text = str(response.code)
            else:
                self.text = f'200 {text}'

        n = int(self.get_argument('n'))
        if n > 0:
            self.get_url(
                self.request.host, self.request.path + f'?n={n - 1}',
                callback=_cb
            )
