# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):

        def callback(element, response):
            self.doc.put('Success callback is called only if there was no error')

        def error_callback(data, response):
            self.doc.put('Error callback works')

        self.post_url(
            self.request.host + self.request.path,
            data={'code': self.get_argument('code')},
            callback=callback,
            error_callback=error_callback
        )

    def post_page(self):
        code = int(self.get_argument('code'))
        raise frontik.handler.HTTPError(code)
