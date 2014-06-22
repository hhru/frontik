# coding=utf-8

import frontik.handler
from frontik.doc import Doc


class Page(frontik.handler.PageHandler):
    def get_page(self):
        a = Doc('a')
        a.put('aaa')
        self.doc.put(a)

        b = Doc('b')
        b.put('bbb')
        self.doc.put(b)

        c = Doc('c')
        self.doc.put(c)
