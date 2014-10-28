import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.json.put(self.post_url(self.request.host + self.request.path))

    def modify_http_client_request(self, request):
        request.headers['X-Foo'] = 'Bar'
        return request

    def post_page(self):
        self.json.put(self.request.headers)
