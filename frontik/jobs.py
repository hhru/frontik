# coding=utf-8

from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import chain_future, dummy_executor, Future
from tornado.ioloop import IOLoop
from tornado.options import options


class IOLoopExecutor(object):
    def __init__(self):
        self._executor = dummy_executor

    def submit(self, fn, *args, **kwargs):
        future = Future()

        def _cb():
            chain_future(self._executor.submit(fn, *args, **kwargs), future)

        IOLoop.instance().add_callback(_cb)
        return future


# Support old interface until all usages are gone
class LegacyMixin(object):
    def add_job(self, func, cb, exception_cb):
        def job_callback(future):
            if future.exception() is not None:
                exception_cb(future.exception())
            else:
                cb(future.result())

        IOLoop.instance().add_future(self.submit(func), job_callback)


class LegacyIOLoopExecutor(IOLoopExecutor, LegacyMixin):
    pass


class LegacyThreadPoolExecutor(ThreadPoolExecutor, LegacyMixin):
    pass


_threadpool_executor = None
_ioloop_executor = LegacyIOLoopExecutor()


def get_executor(executor_type):
    if executor_type == 'threaded':
        global _threadpool_executor
        if _threadpool_executor is None:
            _threadpool_executor = LegacyThreadPoolExecutor(options.executor_pool_size)
        return _threadpool_executor
    elif executor_type == 'ioloop':
        return _ioloop_executor
    else:
        raise ValueError('Invalid value for executor_type: "{0}"'.format(executor_type))
