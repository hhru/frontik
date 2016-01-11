from lxml import etree

import frontik.doc
import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.doc.put(frontik.doc.Doc(root_node='doc'))
        self.doc.put(etree.Element('element', name='Test element'))
        self.doc.put(frontik.doc.Doc(root_node='ok'))
