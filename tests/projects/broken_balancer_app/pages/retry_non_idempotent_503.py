# coding=utf-8

import frontik.handler
from frontik.handler import HTTPError


class Page(frontik.handler.PageHandler):
    def post_page(self):
        raise HTTPError(503, 'broken, retry')
