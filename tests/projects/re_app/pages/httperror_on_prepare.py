# coding=utf-8

from frontik.handler import HTTPError, PageHandler


class Page(PageHandler):
    def prepare(self):
        raise HTTPError(400, headers={'X-Foo': 'Bar'})

    def get_page(self):
        pass
