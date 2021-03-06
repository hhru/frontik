from lxml import etree

import frontik.handler

CDATA_XML = b'<root><![CDATA[test<ba//d>]]></root>'


class Page(frontik.handler.PageHandler):
    def get_page(self):
        def _cb(xml, resp):
            xpath = xml.xpath('/doc/*')
            assert len(xpath) == 1
            assert etree.tostring(xpath[0]) == CDATA_XML

        self.doc.put(
            self.post_url(self.request.host, self.request.path, callback=_cb)
        )

    def post_page(self):
        parser = etree.XMLParser(encoding='UTF-8', strip_cdata=False)
        root = etree.XML(CDATA_XML, parser)
        self.doc.put(root)
