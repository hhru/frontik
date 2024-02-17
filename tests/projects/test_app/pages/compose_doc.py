from lxml import etree

import frontik.handler
from frontik import media_types
from frontik.doc import Doc
from frontik.handler import router


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        invalid_xml = self.get_argument('invalid', 'false')

        self.doc.put(etree.fromstring('<a>aaa</a>'))
        result = await self.post_url(self.request.host, self.request.path, data={'invalid': invalid_xml})
        self.doc.put(result.to_etree_element())
        self.doc.put(Doc('c'))

    @router.post()
    async def post_page(self):
        invalid_xml = self.get_argument('invalid', 'false') == 'true'

        if not invalid_xml:
            self.doc.root_node = etree.Element('bbb')
        else:
            self.set_header('Content-Type', media_types.APPLICATION_XML)
            self.text = 'FAIL'
