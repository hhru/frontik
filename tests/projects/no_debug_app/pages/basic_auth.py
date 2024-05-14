from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/basic_auth', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.require_debug_access('user', 'god')
    handler.json.put({'authenticated': True})
