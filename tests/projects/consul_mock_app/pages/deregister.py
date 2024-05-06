from frontik.handler import PageHandler, get_current_handler
from frontik.routing import regex_router


@regex_router.get(r'^/v1/agent/service/deregister/([a-zA-Z\-_0-9\.:\-]+)', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.set_status(200)
    handler.application.deregistration_call_counter['get_page'] += 1


@regex_router.put(r'^/v1/agent/service/deregister/([a-zA-Z\-_0-9\.:\-]+)', cls=PageHandler)
async def put_page(handler=get_current_handler()):
    handler.set_status(200)
    handler.application.deregistration_call_counter['put_page'] += 1


@regex_router.post(r'^/v1/agent/service/deregister/([a-zA-Z\-_0-9\.:\-]+)', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_status(200)
    handler.application.deregistration_call_counter['post_page'] += 1
