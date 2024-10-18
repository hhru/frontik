from lxml import etree

from frontik.routing import router


@router.get('/simple')
async def get_page():
    handler.set_xsl('simple.xsl')
    handler.doc.put(etree.Element('ok'))
