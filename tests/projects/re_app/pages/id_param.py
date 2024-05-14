import lxml.etree as etree

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import regex_router


@regex_router.get('/id/(?P<id>[^/]+)', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.set_xsl('id_param.xsl')
    handler.doc.put(etree.Element('id', value=handler.get_path_argument('id', 'wrong')))
