import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        old_fetch_request = self.fetch_request

        def new_fetch_request(request, callback, **kwargs):
            request.headers['X-Bar'] = 'Foo'
            old_fetch_request(request, callback, **kwargs)

        self.fetch_request = new_fetch_request
        self.json.put(self.post_url(self.request.host + self.request.path))

    def fetch_request(self, request, callback, add_to_finish_group=True):
        request.headers['X-Foo'] = 'Bar'
        return super(Page, self).fetch_request(request, callback, add_to_finish_group=add_to_finish_group)

    def post_page(self):
        self.json.put(self.request.headers)
