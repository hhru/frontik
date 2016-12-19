# coding=utf-8

from frontik.handler import PageHandler


class Page(PageHandler):
    def prepare(self):
        raise ValueError('FAIL')
