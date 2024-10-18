from frontik.routing import router
from fastapi import Request


@router.get('/v1/agent/service/register')
async def get_page(request: Request):
    request.app.registration_call_counter['get_page'] += 1


@router.put('/v1/agent/service/register')
async def put_page(request: Request):
    request.app.registration_call_counter['put_page'] += 1


@router.post('/v1/agent/service/register')
async def post_page(request: Request):
    request.app.registration_call_counter['post_page'] += 1
