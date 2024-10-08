from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


class Page(PageHandler):
    @staticmethod
    def modify_http_client_request(handler, balanced_request):
        super().modify_http_client_request(handler, balanced_request)
        balanced_request.headers['X-Foo'] = 'Bar'


@plain_router.get('/http_client/custom_headers', cls=Page)
async def get_page(handler=get_current_handler()):
    result = await handler.post_url(handler.get_header('host'), handler.path)
    handler.json.put(result.data)


@plain_router.post('/http_client/custom_headers', cls=Page)
async def post_page(handler: Page = get_current_handler()):
    handler.json.put(handler.request.headers)
