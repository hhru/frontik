import time

import tornado.ioloop

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.get_url_retry('localhost:{0}/page/long_page/'.format(self.get_argument('port')),
                            callback=self.step2)

    def step2(self, xml, response):
        if response.error:
            self.doc.put('error')
        else:
            self.doc.put('ok')
