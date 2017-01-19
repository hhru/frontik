# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):

        def callback_post(text, response):
            self.text = text

        self.post_url(self.request.host + self.request.path, callback=callback_post)

    def post_page(self):
        self.add_header('Content-Type', 'text/plain')
        self.text = 'post_url success'
