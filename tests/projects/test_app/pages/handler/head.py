from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.head('/handler/head', cls=PageHandler)
async def head_page(handler=get_current_handler()):
    handler.set_header('X-Foo', 'Bar')
    handler.text = 'response body must be empty for HEAD requests'
