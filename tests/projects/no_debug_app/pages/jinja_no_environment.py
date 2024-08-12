from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/jinja_no_environment', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.set_template('empty.html')
    handler.json.put({'x': 'y'})
