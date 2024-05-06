from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/finish', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    code = int(handler.get_query_argument('code', '200'))

    handler.set_header('x-foo', 'Bar')
    handler.set_status(code)

    handler.finish('success')
