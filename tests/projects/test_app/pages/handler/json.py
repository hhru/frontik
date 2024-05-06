from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


class Page(PageHandler):
    def _page_handler(self) -> None:
        self.text = self.get_body_argument('foo')


@router.post('/handler/json', cls=Page)
async def post_page(handler=get_current_handler()):
    return handler._page_handler()


@router.put('/handler/json', cls=Page)
async def put_page(handler=get_current_handler()):
    return handler._page_handler()
