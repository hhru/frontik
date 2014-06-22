import lxml.etree as etree

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.set_xsl('id_param.xsl')
        for id_val in self.get_arguments('id', 'wrong'):
            self.doc.put(etree.Element('id', value=id_val))
