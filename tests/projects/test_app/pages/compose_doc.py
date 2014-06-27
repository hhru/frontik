# coding=utf-8

from lxml import etree

import frontik.handler
from frontik.doc import Doc


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self_uri = self.request.host + self.request.path
        invalid_xml = self.get_argument('invalid', 'false')

        self.doc.put(Doc('a').put('aaa'))
        self.doc.put(self.post_url(self_uri, data={'invalid': invalid_xml}))
        self.doc.put(Doc('c'))

    def post_page(self):
        invalid_xml = self.get_argument('invalid', 'false') == 'true'

        if not invalid_xml:
            self.doc.root_node = etree.Element('bbb')
        else:
            self.set_header('Content-Type', 'application/xml')
            self.text = 'FAIL'
