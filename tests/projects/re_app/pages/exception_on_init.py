# coding=utf-8

from frontik.handler import PageHandler


class Page(PageHandler):
    def __init__(self, *args, **kwargs):
        raise ValueError('FAIL')
