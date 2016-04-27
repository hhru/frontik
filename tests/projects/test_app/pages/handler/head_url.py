# coding=utf-8

from frontik import http_codes
import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):

        def _cb(data, response):
            if data == '' and response.code == http_codes.OK:
                self.text = 'OK'

        self.head_url(self.request.host+'/handler/head', callback=_cb)
