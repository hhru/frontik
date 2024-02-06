from lxml import etree

import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        self.set_xsl('syntax_error.xsl')
        self.doc.put(etree.Element('ok'))
