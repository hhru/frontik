import frontik.handler
from frontik import etree

class Page(frontik.handler.PageHandler):
    def get(self):
        if not self.get_argument('noxsl', None):
            self.set_xsl('simple.xsl')

        self.doc.put(etree.Element('ok'))

        self.finish_page()
