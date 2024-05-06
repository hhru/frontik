from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/v1/agent/service/register', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.set_status(200)
    handler.application.registration_call_counter['get_page'] += 1


@router.put('/v1/agent/service/register', cls=PageHandler)
async def put_page(handler=get_current_handler()):
    handler.set_status(200)
    handler.application.registration_call_counter['put_page'] += 1


@router.post('/v1/agent/service/register', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_status(200)
    handler.application.registration_call_counter['post_page'] += 1
