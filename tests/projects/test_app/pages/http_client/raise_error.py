from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


class Page(PageHandler):
    def send_error(self, status_code=500, exc_info=None, **kwargs):
        if isinstance(exc_info[1], UnicodeEncodeError):
            self.finish('UnicodeEncodeError')


@plain_router.get('/http_client/raise_error', cls=Page)
async def get_page(handler=get_current_handler()):
    await handler.post_url(handler.get_header('host'), '/a-вот')
