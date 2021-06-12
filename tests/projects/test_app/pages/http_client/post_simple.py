from frontik import handler, media_types


class Page(handler.PageHandler):
    async def get_page(self):

        def callback_post(text, response):
            self.text = text

        self.post_url(self.request.host, self.request.path, callback=callback_post)

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'post_url success'
