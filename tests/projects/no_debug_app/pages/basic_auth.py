from frontik.auth import check_debug_auth_or_finish
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/basic_auth', cls=PageHandler)
async def get_page(handler: PageHandler = get_current_handler()) -> None:
    check_debug_auth_or_finish(handler, 'user', 'god')
    handler.json.put({'authenticated': True})
