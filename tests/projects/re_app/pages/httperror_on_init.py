# coding=utf-8

from frontik.handler import HTTPError, PageHandler


class Page(PageHandler):
    def __init__(self, *args, **kwargs):
        raise HTTPError(401)
