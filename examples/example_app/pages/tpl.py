from fastapi import Request

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/tpl', cls=PageHandler)
def get_page(request: Request, handler: PageHandler = get_current_handler()) -> None:
    handler.set_template('main.html')  # This template is located in the `templates` folder
    handler.json.put(handler.get_url(request.headers.get('host', ''), '/example'))
