from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/jinja_custom_environment', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.set_template('jinja_custom_environment.html')
    handler.json.put({})
