from lxml import etree

from frontik.handler import HTTPErrorWithPostprocessors, PageHandler, get_current_handler
from frontik.routing import router


@router.get('/xsl/simple', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.set_xsl(handler.get_query_argument('template', 'simple.xsl'))
    handler.doc.put(etree.Element('ok'))

    if handler.get_query_argument('raise', 'false') == 'true':
        handler.doc.put(etree.Element('not-ok'))
        raise HTTPErrorWithPostprocessors(400)
