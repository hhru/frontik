from lxml import etree

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


class Page(PageHandler):
    @staticmethod
    def extract_metainfo_pp(handler, _, meta_info):
        return ','.join(meta_info)


@plain_router.get('/postprocess_xsl', cls=Page)
async def get_page(handler=get_current_handler()):
    handler.set_xsl('meta.xsl')
    handler.doc.put(etree.Element('ok', key=handler.get_query_argument('meta_key', '')))
    handler.add_render_postprocessor(handler.extract_metainfo_pp)
