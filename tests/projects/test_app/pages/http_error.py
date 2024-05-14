from fastapi import HTTPException

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/http_error', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    code = int(handler.get_query_argument('code', '200'))
    raise HTTPException(code)
