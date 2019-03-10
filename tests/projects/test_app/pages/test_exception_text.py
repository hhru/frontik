import asyncio

from frontik.handler import HTTPErrorWithPostprocessors, PageHandler


class Page(PageHandler):
    def get_page(self):
        def callback_post(element, response):
            assert False

        self.add_postprocessor(self.async_pp)
        self.post_url(self.request.host, self.request.path, callback=callback_post)
        self.post_url(self.request.host, self.request.path, callback=callback_post)
        self.post_url(self.request.host, self.request.path, callback=callback_post)
        self.post_url(self.request.host, self.request.path, callback=callback_post)

        self.text = 'This is just a plain text'
        raise HTTPErrorWithPostprocessors(403)

    async def async_pp(self, _):
        await asyncio.sleep(0)
