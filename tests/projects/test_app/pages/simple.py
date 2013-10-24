# coding=utf-8

import lxml.etree as etree

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.set_xsl('simple.xsl')
        self.doc.put(etree.Element('ok'))
