from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


class Page(PageHandler):
    def _page_handler(self) -> None:
        self.text = self.get_body_argument('foo', 'baz')


@plain_router.post('/handler/json_optional_args', cls=Page)
async def post_page(handler=get_current_handler()):
    return handler._page_handler()


@plain_router.put('/handler/json_optional_args', cls=Page)
async def put_page(handler=get_current_handler()):
    return handler._page_handler()
