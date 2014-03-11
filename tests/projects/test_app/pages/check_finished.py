# coding=utf-8

import tornado.ioloop

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        def callback():
            Page.result = 'Error'

        self.add_callback(self.check_finished(callback))
        self.finish(getattr(Page, 'result', ''))
