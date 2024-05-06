from lxml import etree

from frontik import media_types
from frontik.doc import Doc
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/compose_doc', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    invalid_xml = handler.get_query_argument('invalid', 'false')

    handler.doc.put(etree.fromstring('<a>aaa</a>'))
    result = await handler.post_url(handler.get_header('host'), handler.path, data={'invalid': invalid_xml})
    handler.doc.put(result.to_etree_element())
    handler.doc.put(Doc('c'))


@router.post('/compose_doc', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    invalid_xml = handler.get_body_argument('invalid', 'false') == 'true'

    if not invalid_xml:
        handler.doc.root_node = etree.Element('bbb')
    else:
        handler.set_header('Content-Type', media_types.APPLICATION_XML)
        handler.text = 'FAIL'
