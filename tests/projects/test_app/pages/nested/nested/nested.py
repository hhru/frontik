from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/nested/nested/nested', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.text = 'OK'
