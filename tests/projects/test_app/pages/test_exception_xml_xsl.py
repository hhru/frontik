import frontik.handler
import lxml.etree as etree

class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.doc.put(etree.Element('lololo'))
        raise frontik.handler.HTTPError(status_code=202, xml = etree.Element('ok'), xsl = 'simple.xsl')
        self.doc.put("absolutely not forty two, no way")
