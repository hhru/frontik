from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/arguments', cls=PageHandler)
async def get_page(handler: PageHandler = get_current_handler()) -> None:
    handler.json.put({'тест': handler.get_argument('param')})
