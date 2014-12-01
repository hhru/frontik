# coding=utf-8

import time

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.post_url(
            self.request.host + self.request.path,
            callback=self.request_callback, request_timeout=0.5
        )

    def request_callback(self, xml, response):
        if response.error:
            self.doc.put('error')
        else:
            self.doc.put('ok')

    def post_page(self):
        self.add_timeout(
            time.time() + 2, self.finish_group.add(self.check_finished(self.timeout_callback))
        )

    def timeout_callback(self):
        self.doc.put('ok!')
