from lxml import etree

import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.set_xsl('simple.xsl')
        self.doc.put(etree.Element('ok'))
