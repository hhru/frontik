from lxml import etree

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/xsl/parse_error', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.set_xsl('parse_error.xsl')
    handler.doc.put(etree.Element('ok'))
