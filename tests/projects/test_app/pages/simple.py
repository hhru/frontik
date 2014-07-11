# coding=utf-8

from lxml import etree

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.set_xsl(self.get_argument('template', 'simple.xsl'))
        self.doc.put(etree.Element('ok'))
