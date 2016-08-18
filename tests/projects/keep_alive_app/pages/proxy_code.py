# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):

        def callback(element, response):
            if response.error:
                self.finish(str(response.error.code))
            else:
                self.finish(str(response.code))

        self.get_url('http://127.0.0.1:' + self.get_argument('port'), request_timeout=0.1, callback=callback)
