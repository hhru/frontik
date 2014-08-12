# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.text = 'old bad text'

        def callback_post(element, response):
            assert False

        self_uri = self.request.host + self.request.path
        self.post_url(self_uri, callback=callback_post)
        self.post_url(self_uri, callback=callback_post)
        self.post_url(self_uri, callback=callback_post)
        self.post_url(self_uri, callback=callback_post)

        raise frontik.handler.HTTPError(403, text='This is just a plain text')
