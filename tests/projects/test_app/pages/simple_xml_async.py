from lxml import etree

import frontik.doc
import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        self.doc.put(frontik.doc.Doc())
        self.doc.put(etree.Element('element', name='Test element'))
        self.doc.put(frontik.doc.Doc(root_node='ok'))
