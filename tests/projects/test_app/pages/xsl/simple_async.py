from lxml import etree

from frontik.handler import HTTPErrorWithPostprocessors, PageHandler


class Page(PageHandler):
    async def get_page(self):
        self.set_xsl(self.get_argument('template', 'simple.xsl'))
        self.doc.put(etree.Element('ok'))

        if self.get_argument('raise', 'false') == 'true':
            self.doc.put(etree.Element('not-ok'))
            raise HTTPErrorWithPostprocessors(400)
