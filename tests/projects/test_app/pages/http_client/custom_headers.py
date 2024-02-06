import frontik.handler
from frontik.handler import router

class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        result = await self.post_url(self.request.host, self.request.path)
        self.json.put(result.data)

    def modify_http_client_request(self, balanced_request):
        super().modify_http_client_request(balanced_request)
        balanced_request.headers['X-Foo'] = 'Bar'

    @router.post()
    async def post_page(self):
        self.json.put(self.request.headers)
