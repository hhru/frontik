from lxml import etree

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/simple', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.set_xsl('simple.xsl')
    handler.doc.put(etree.Element('ok'))
