from tornado import gen

import frontik.handler


@gen.coroutine
def some_async_function(handler):
    yield handler.post_url(handler.request.host, handler.request.path)
    return 1 / 0


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.finish_group.add_future(some_async_function(self))

    def post_page(self):
        self.text = 'result'
