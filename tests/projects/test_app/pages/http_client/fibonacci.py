# coding=utf-8

import frontik.doc
import frontik.handler
import frontik.async


class Page(frontik.handler.PageHandler):
    def get_page(self):
        n = int(self.get_argument('n'))
        self_uri = self.request.host + self.request.path

        if n >= 2:
            self.acc = 0

            def intermediate_cb(xml, response):
                self.acc += int(xml.text)

            def final_cb():
                self.log.debug('n=%s', self.acc)
                self.doc.put(str(self.acc))

            grp = frontik.async.AsyncGroup(final_cb, name='acc')

            self.get_url(self_uri, {'n': str(n - 1)}, callback=grp.add(intermediate_cb))
            self.get_url(self_uri, {'n': str(n - 2)}, callback=grp.add(intermediate_cb))
        else:
            self.doc.put('1')
