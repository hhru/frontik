# coding=utf-8

import tornado.options
from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import chain_future, DummyExecutor, Future
from tornado.ioloop import IOLoop


class IOLoopExecutor(object):
    def __init__(self):
        self._executor = DummyExecutor()

    def submit(self, fn, *args, **kwargs):
        future = Future()

        def _cb():
            chain_future(self._executor.submit(fn, *args, **kwargs), future)

        IOLoop.instance().add_callback(_cb)
        return future

_threadpool_executor = None
_ioloop_executor = IOLoopExecutor()


def get_executor(executor_type):
    if executor_type == 'threaded':
        global _threadpool_executor
        if _threadpool_executor is None:
            _threadpool_executor = ThreadPoolExecutor(tornado.options.options.executor_pool_size)
        return _threadpool_executor
    elif executor_type == 'ioloop':
        return IOLoopExecutor()
    else:
        raise ValueError('Invalid value for executor_type: "{0}"'.format(executor_type))
