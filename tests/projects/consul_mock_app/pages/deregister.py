from fastapi import Request

from frontik.routing import router


@router.get('/v1/agent/service/deregister/{service}')
async def get_page(request: Request) -> None:
    request.app.deregistration_call_counter['get_page'] += 1


@router.put('/v1/agent/service/deregister/{service}')
async def put_page(request: Request) -> None:
    request.app.deregistration_call_counter['put_page'] += 1


@router.post('/v1/agent/service/deregister/{service}')
async def post_page(request: Request) -> None:
    request.app.deregistration_call_counter['post_page'] += 1
