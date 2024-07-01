from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/arguments', cls=PageHandler)
async def get_page(handler: PageHandler = get_current_handler()) -> None:
    handler.json.put({'тест': handler.get_argument('param')})
