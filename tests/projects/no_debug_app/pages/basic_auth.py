# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.require_debug_access('user', 'god')
        self.doc.put('authenticated!')
