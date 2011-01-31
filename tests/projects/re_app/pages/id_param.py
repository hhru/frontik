import lxml.etree as etree

import frontik.handler

class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.set_xsl('id_param.xsl')
        self.doc.put(etree.Element('id',value=self.get_argument('id', 'wrong')))
