import lxml.etree as etree

import frontik.handler

class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.set_xsl('parse_error.xsl')

        self.doc.put(etree.Element('ok'))
