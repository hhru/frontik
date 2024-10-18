from lxml import etree

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/simple', cls=PageHandler)
async def get_page1(handler=get_current_handler()):
    return await get_page(handler)


@router.get('/not_simple', cls=PageHandler)
async def get_page2(handler: PageHandler = get_current_handler()) -> None:
    return await get_page(handler)


async def get_page(handler: PageHandler) -> None:
    handler.set_xsl('simple.xsl')
    handler.doc.put(etree.Element('ok'))
