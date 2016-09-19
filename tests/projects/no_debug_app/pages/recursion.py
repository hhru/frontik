# coding=utf-8

from tornado.escape import to_unicode

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        def _cb(text, response):
            self.set_header('Content-Type', 'text/plain')
            if response.error:
                self.text = str(response.code)
            else:
                self.text = u'200 {}'.format(to_unicode(text))

        n = int(self.get_argument('n'))
        if n > 0:
            self.get_url(
                self.request.host + self.request.path + '?n={}'.format(n - 1),
                callback=_cb
            )
