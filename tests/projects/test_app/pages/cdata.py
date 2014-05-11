# coding=utf-8

from lxml import etree

import frontik.handler

CDATA_XML = '<root><![CDATA[test<ba//d>]]></root>'


class Page(frontik.handler.PageHandler):
    def get_page(self):
        def _cb(xml, resp):
            xpath = xml.xpath('/doc/*')
            assert len(xpath) == 1
            assert etree.tostring(xpath[0]) == CDATA_XML

        self.post_url('http://localhost:{}/test_app/cdata'.format(self.get_argument('port')), callback=_cb)

    def post_page(self):
        parser = etree.XMLParser(strip_cdata=False)
        root = etree.XML(CDATA_XML, parser)
        self.doc.put(root)
