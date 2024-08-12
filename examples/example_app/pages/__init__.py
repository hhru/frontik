from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/tpl', cls=PageHandler)
def get_page(handler: PageHandler = get_current_handler()) -> None:
    handler.json.put({'text': 'Hello, world!'})
