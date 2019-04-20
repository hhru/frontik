from tornado.escape import to_unicode

from frontik.handler import HTTPErrorWithPostprocessors, PageHandler


class Page(PageHandler):
    def get_page(self):
        self.json.put(self.post_url(self.request.host, self.request.path, parse_on_error=True))
        self.json.put(self.put_url(self.request.host, self.request.path, parse_on_error=False))

        result = yield self.delete_url(self.request.host, self.request.path, parse_response=False)
        if not result.failed:
            self.json.put({'delete': to_unicode(result.data)})

    def post_page(self):
        self.json.put({'post': True})
        raise HTTPErrorWithPostprocessors(400)

    def put_page(self):
        self.json.put({'put': True})
        raise HTTPErrorWithPostprocessors(400)

    def delete_page(self):
        self.text = 'deleted'
