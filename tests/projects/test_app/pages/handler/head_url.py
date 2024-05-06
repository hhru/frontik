import http.client

from fastapi import Request

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/handler/head_url', cls=PageHandler)
async def get_page(request: Request, handler: PageHandler = get_current_handler()) -> None:
    head_result = await handler.head_url(request.headers.get('host', ''), '/handler/head', name='head')

    if head_result.raw_body == b'' and head_result.status_code == http.client.OK:
        handler.text = 'OK'
