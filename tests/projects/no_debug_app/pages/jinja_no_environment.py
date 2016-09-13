# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.set_template('empty.html')
        self.json.put({'x': 'y'})
