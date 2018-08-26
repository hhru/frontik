# coding=utf-8

from tornado.web import HTTPError

from frontik.handler import PageHandler


class Page(PageHandler):
    def get_page(self):
        self.post_url(self.request.host, self.request.path, fail_fast=True)

    def get_page_fail_fast(self, failed_future):
        self.set_status(403)

    def post_page(self):
        raise HTTPError(403)
