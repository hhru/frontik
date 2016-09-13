# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.set_template('jinja_custom_environment.html')
        self.json.put({})
