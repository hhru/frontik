from lxml import etree

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router

CDATA_XML = b'<root><![CDATA[test<ba//d>]]></root>'


@plain_router.get('/cdata', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    result = await handler.post_url(handler.get_header('host'), handler.path)

    xpath = result.data.xpath('/doc/*')
    assert len(xpath) == 1
    assert etree.tostring(xpath[0]) == CDATA_XML

    handler.doc.put(xpath)


@plain_router.post('/cdata', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    parser = etree.XMLParser(encoding='UTF-8', strip_cdata=False)
    root = etree.XML(CDATA_XML, parser)
    handler.doc.put(root)
