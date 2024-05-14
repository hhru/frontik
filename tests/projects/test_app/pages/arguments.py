from fastapi import Request

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router
from frontik.util import tornado_parse_qs_bytes


@router.get('/arguments', cls=PageHandler)
async def get_page(request: Request, handler: PageHandler = get_current_handler()) -> None:
    if handler.get_bool_argument('enc', False):
        qs = tornado_parse_qs_bytes(request.scope['query_string'])
        param = qs.get('param', [])[0]
        handler.json.put({'тест': handler.decode_argument(param)})
    else:
        handler.json.put({'тест': handler.get_query_argument('param')})
