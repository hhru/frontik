from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/finish_204', cls=PageHandler)
async def get_page(handler: PageHandler = get_current_handler()) -> None:
    handler.text = 'data'
    handler.set_status(204)
