import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        self.json.put(self.post_url(self.request.host, self.request.path))

    def modify_http_client_request(self, balanced_request):
        super().modify_http_client_request(balanced_request)
        balanced_request.headers['X-Foo'] = 'Bar'

    async def post_page(self):
        self.json.put(self.request.headers)
