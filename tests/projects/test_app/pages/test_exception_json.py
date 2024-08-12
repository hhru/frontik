from frontik.handler import HTTPErrorWithPostprocessors, PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/test_exception_json', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.json.put({'reason': 'bad argument'})
    raise HTTPErrorWithPostprocessors(400)
