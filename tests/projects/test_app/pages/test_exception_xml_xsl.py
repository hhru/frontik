import frontik.handler
from lxml import etree


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.doc.put(etree.Element('not-ok'))
        raise frontik.handler.HTTPError(302, xml=etree.Element('ok'), xsl='simple.xsl')
        self.doc.put("absolutely not forty two, no way")
