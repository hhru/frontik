# coding=utf-8

import http.client

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):

        def _cb(data, response):
            if data == b'' and response.code == http.client.OK:
                self.text = 'OK'

        self.head_url(self.request.host, '/handler/head', callback=_cb)
