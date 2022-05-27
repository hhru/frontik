from lxml import etree

import frontik.handler

CDATA_XML = b'<root><![CDATA[test<ba//d>]]></root>'


class Page(frontik.handler.AwaitablePageHandler):
    async def get_page(self):
        request = self.post_url(self.request.host, self.request.path)
        self.doc.put(request)
        result = await request

        xpath = result.data.xpath('/doc/*')
        assert len(xpath) == 1
        assert etree.tostring(xpath[0]) == CDATA_XML

    async def post_page(self):
        parser = etree.XMLParser(encoding='UTF-8', strip_cdata=False)
        root = etree.XML(CDATA_XML, parser)
        self.doc.put(root)
