from fastapi import Request
from fastapi.responses import ORJSONResponse, Response

from frontik.routing import router


@router.get('/index')
async def echo_handler(_: Request) -> Response:
    return ORJSONResponse(content={'ok': 200})
