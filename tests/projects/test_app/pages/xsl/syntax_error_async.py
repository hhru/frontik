from lxml import etree

import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.set_xsl('syntax_error.xsl')
        self.doc.put(etree.Element('ok'))
