from asyncio import CancelledError

from tornado import gen

import frontik.handler


class Page(frontik.handler.PageHandler):
    data = {}

    def get_page(self):
        if not self.data:
            self.json.put({'get': True})
            self.coro()
        else:
            while not all(x in self.data for x in ('put_made', 'post_made', 'delete_cancelled')):
                yield gen.sleep(0.05)

            self.json.put(self.data)
            self.data = {}

    def finish(self, chunk=None):
        super(Page, self).finish(chunk)
        if self.request.method == 'GET':
            # HTTP requests with waited=False can be made after handler is finished
            self.json.put(self.put_url(self.request.host, self.request.path, waited=False))

    @gen.coroutine
    def coro(self):
        result = yield self.post_url(self.request.host, self.request.path, waited=False)
        self.json.put(result)

        # HTTP requests with waited=True are aborted after handler is finished
        try:
            yield self.delete_url(self.request.host, self.request.path, waited=True)
        except CancelledError:
            self.record_request({'delete_cancelled': True})

    def post_page(self):
        self.record_request({'post_made': True})

    def put_page(self):
        self.record_request({'put_made': True})

    def delete_page(self):
        self.record_request({'delete_made': True})

    def record_request(self, data):
        self.json.put(data)
        Page.data.update(data)
