import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.json.put({'get': True})

        self.json.put(self.post_url(self.request.host, self.request.path, add_to_finish_group=False))
        self.json.put(self.put_url(self.request.host, self.request.path, add_to_finish_group=False))
        self.json.put(self.delete_url(self.request.host, self.request.path, add_to_finish_group=False))

    def post_page(self):
        self.json.put({'post': True})

    def put_page(self):
        self.json.put({'put': True})

    def delete_page(self):
        self.json.put({'delete': True})
