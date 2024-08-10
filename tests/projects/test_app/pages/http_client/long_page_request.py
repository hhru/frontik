from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


class Page(PageHandler):
    def request_callback(self, xml: str, error: bool) -> None:
        self.json.put({'error_received': bool(error)})


@plain_router.get('/http_client/long_page_request', cls=Page)
async def get_page(handler=get_current_handler()):
    result = await handler.post_url(handler.get_header('host'), handler.path, request_timeout=0.5)
    handler.request_callback(result.data, result.failed)
