# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):

        def callback_post(element, response):
            self.doc.put(element.text)

        self.post_url(self.request.host + self.request.path, callback=callback_post)

    def post_page(self):
        self.doc.put('42')
