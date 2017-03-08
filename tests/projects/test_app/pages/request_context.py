# coding=utf-8

from functools import partial

from tornado.concurrent import Future
from tornado.gen import coroutine
from tornado.stack_context import NullContext, wrap

from frontik.handler import PageHandler
from frontik.jobs import get_executor
from frontik.request_context import RequestContext


def _callback(name, handler):
    handler.json.put({name: RequestContext.get('handler_name')})


class Page(PageHandler):
    def get_page(self):
        def _waited_callback(name):
            return self.finish_group.add(partial(_callback, name, self))

        self.json.put({'page': RequestContext.get('handler_name')})

        self.add_callback(_waited_callback('callback'))

        with NullContext():
            self.add_callback(_waited_callback('null_context_callback'))

        get_executor('threaded').submit(_waited_callback('executor'))

        get_executor('threaded').submit(wrap(_waited_callback('executor_wrapped')))

        self.add_future(self.run_coroutine(), self.finish_group.add_notification())

    @coroutine
    def run_coroutine(self):
        self.json.put({'coroutine_before_yield': RequestContext.get('handler_name')})

        future = Future()
        future.set_result(None)
        yield future

        self.json.put({'coroutine_after_yield': RequestContext.get('handler_name')})

    def __repr__(self):
        return 'request_context'
