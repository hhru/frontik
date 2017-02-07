# coding=utf-8

from frontik.handler import PageHandler

from tornado.httpclient import HTTPRequest


class Page(PageHandler):
    def get_page(self):
        def callback_fetch(response):
            self.text = response.body

        request = HTTPRequest(self.request.host + self.request.path, method='POST', body='')

        self._http_client.fetch(request, callback_fetch)

    def post_page(self):
        self.text = 'fetch success'
