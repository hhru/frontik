import json

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/call_registration_stat', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.set_status(200)
    handler.text = json.dumps(handler.application.registration_call_counter)
