import lxml.etree as etree

import frontik.handler
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        self.set_xsl('id_param.xsl')
        self.doc.put(etree.Element('id', value=self.get_argument('id', 'wrong')))
