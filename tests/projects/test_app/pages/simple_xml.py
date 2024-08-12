from lxml import etree

import frontik.doc
import frontik.handler
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/simple_xml', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.doc.put(frontik.doc.Doc())
    handler.doc.put(etree.Element('element', name='Test element'))
    handler.doc.put(frontik.doc.Doc(root_node='ok'))
