from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/include_xml', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.doc.put(handler.xml_from_file('aaa.xml'))
