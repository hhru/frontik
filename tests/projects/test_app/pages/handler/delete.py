from fastapi import Request

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/handler/delete', cls=PageHandler)
async def get_page(request: Request, handler: PageHandler = get_current_handler()) -> None:
    result = await handler.delete_url('http://' + request.headers.get('host', ''), handler.path, data={'data': 'true'})
    if not result.failed:
        handler.json.put(result.data)


@router.post('/handler/delete', cls=PageHandler)
async def post_page(handler: PageHandler = get_current_handler()) -> None:
    result = await handler.delete_url('http://backend', handler.path, fail_fast=True)
    if not result.failed:
        handler.json.put(result.data)


@router.delete('/handler/delete', cls=PageHandler)
async def delete_page(handler: PageHandler = get_current_handler()) -> None:
    handler.json.put({'delete': handler.get_query_argument('data')})
