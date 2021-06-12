from frontik.handler import HTTPErrorWithPostprocessors, PageHandler


class Page(PageHandler):
    async def get_page(self):
        def callback_post(element, response):
            assert False

        self.post_url(self.request.host, self.request.path, callback=callback_post)
        self.post_url(self.request.host, self.request.path, callback=callback_post)
        self.post_url(self.request.host, self.request.path, callback=callback_post)
        self.post_url(self.request.host, self.request.path, callback=callback_post)

        self.text = 'This is just a plain text'
        raise HTTPErrorWithPostprocessors(403)
