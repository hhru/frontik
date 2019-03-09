from concurrent.futures import ThreadPoolExecutor
from functools import partial

from tornado.gen import coroutine

from frontik import request_context
from frontik.handler import PageHandler


def _callback(name, handler, *args):
    handler.json.put({name: request_context.get_handler_name()})


class Page(PageHandler):
    def get_page(self):
        def _waited_callback(name):
            return self.finish_group.add(partial(_callback, name, self))

        self.json.put({'page': request_context.get_handler_name()})

        self.add_callback(_waited_callback('callback'))

        ThreadPoolExecutor(1).submit(_waited_callback('executor'))

        self.add_future(self.run_coroutine(), self.finish_group.add_notification())

        future = self.post_url(self.request.host, self.request.uri)
        self.add_future(future, _waited_callback('future'))

    @coroutine
    def run_coroutine(self):
        self.json.put({'coroutine_before_yield': request_context.get_handler_name()})

        yield self.post_url(self.request.host, self.request.uri)

        self.json.put({'coroutine_after_yield': request_context.get_handler_name()})

    def post_page(self):
        pass

    def __repr__(self):
        return 'request_context'
