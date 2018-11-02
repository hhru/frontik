# coding=utf-8

from tornado.web import HTTPError

from frontik.handler import PageHandler


class Page(PageHandler):
    def get_page(self):
        return {
            'POST': self.POST(self.request.host, self.request.path, fail_on_error=True)
        }

    @staticmethod
    def get_page_requests_failed(name, data, response):
        raise HTTPError(403)

    def post_page(self):
        raise HTTPError(403)
