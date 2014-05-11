# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.get_url(
            'localhost:{}/page/long_page/'.format(self.get_argument('port')),
            callback=self.step2, request_timeout=0.5
        )

    def step2(self, xml, response):
        if response.error:
            self.doc.put('error')
        else:
            self.doc.put('ok')
