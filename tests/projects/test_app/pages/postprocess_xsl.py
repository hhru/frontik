from lxml import etree

from frontik.handler import PageHandler


class Page(PageHandler):
    @staticmethod
    def extract_metainfo_pp(handler, _, meta_info):
        return ','.join(meta_info)

    async def get_page(self):
        self.set_xsl('meta.xsl')
        self.doc.put(etree.Element('ok', key=self.get_argument('meta_key', '')))
        self.add_render_postprocessor(self.extract_metainfo_pp)
