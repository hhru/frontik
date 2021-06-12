from lxml import etree

import frontik.doc
import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.doc.put(frontik.doc.Doc())
        self.doc.put(etree.Element('element', name='Test element'))
        self.doc.put(frontik.doc.Doc(root_node='ok'))
