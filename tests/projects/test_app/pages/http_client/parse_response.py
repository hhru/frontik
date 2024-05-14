from tornado.escape import to_unicode

from frontik.handler import HTTPErrorWithPostprocessors, PageHandler, get_current_handler
from frontik.routing import router


@router.get('/http_client/parse_response', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    result = await handler.post_url(handler.get_header('host'), handler.path, parse_on_error=True)
    handler.json.put(result.data)
    result = await handler.put_url(handler.get_header('host'), handler.path, parse_on_error=False)
    handler.json.put(result.to_dict())

    result = await handler.delete_url(handler.get_header('host'), handler.path, parse_response=False)
    if not result.failed:
        handler.json.put({'delete': to_unicode(result.data)})


@router.post('/http_client/parse_response', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.json.put({'post': True})
    raise HTTPErrorWithPostprocessors(400)


@router.put('/http_client/parse_response', cls=PageHandler)
async def put_page(handler=get_current_handler()):
    handler.json.put({'put': True})
    raise HTTPErrorWithPostprocessors(400)


@router.delete('/http_client/parse_response', cls=PageHandler)
async def delete_page(handler=get_current_handler()):
    handler.text = 'deleted'
