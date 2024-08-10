import json

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/call_deregistration_stat', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.set_status(200)
    handler.text = json.dumps(handler.application.deregistration_call_counter)
