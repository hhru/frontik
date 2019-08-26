from tornado import gen

from frontik.handler import PageHandler


class Page(PageHandler):
    data = {}

    def get_page(self):
        if self.request.method == 'HEAD':
            self.head_page()
            return

        if not self.data:
            # HTTP request with waited=False and fail_fast=True should not influence responses to client
            yield self.head_url(self.request.host, self.request.path, waited=False, fail_fast=True)
            yield self.post_url(self.request.host, self.request.path, waited=False, fail_fast=True)
            yield self.put_url(self.request.host, self.request.path, waited=False, fail_fast=True)
            yield self.delete_url(self.request.host, self.request.path, waited=False, fail_fast=True)

            self.json.put({'get': True})
        else:
            self.json.put(self.data)
            self.data = {}

    @gen.coroutine
    def head_page(self):
        self._record_failed_request({'head_failed': True})

    def post_page(self):
        self._record_failed_request({'post_failed': True})

    def put_page(self):
        self._record_failed_request({'put_failed': True})

    def delete_page(self):
        self._record_failed_request({'delete_failed': True})

    def _record_failed_request(self, data):
        Page.data.update(data)
        raise ValueError('Some error')
