import time
import logging
from functools import wraps

from tornado.ioloop import IOLoop
from tornado.concurrent import Future

async_logger = logging.getLogger('frontik.futures')


# AsyncGroup will become legacy in future releases
# It will be replaced with FutureGroup
class AsyncGroup:
    """
    Grouping of several async requests and final callback in such way that final callback is invoked
    after the last request is finished.

    If any callback throws an exception, all pending callbacks would be aborted and finish_cb
    would not be automatically called.
    """

    def __init__(self, finish_cb, name=None):
        self._counter = 0
        self._finish_cb = finish_cb
        self._finished = False
        self._aborted = False
        self._name = name
        self._future = Future()
        self._start_time = time.time()

    def abort(self):
        async_logger.info('aborting %s', self)
        self._aborted = True

    def finish(self):
        if self._finished:
            async_logger.warning('trying to finish already finished %s', self)
            return

        async_logger.debug('%s done in %.2fms', self, (time.time() - self._start_time) * 1000.)
        self._finished = True
        self._future.set_result(None)

        try:
            self._finish_cb()
        finally:
            # prevent possible cycle references
            self._finish_cb = None

    def try_finish(self):
        if self._counter == 0:
            self.finish()

    def try_finish_async(self):
        """Executes finish_cb in next IOLoop iteration"""
        if self._counter == 0:
            IOLoop.current().add_callback(self.finish)

    def _inc(self):
        assert not self._finished
        self._counter += 1

    def _dec(self):
        self._counter -= 1

    def add(self, intermediate_cb):
        self._inc()

        @wraps(intermediate_cb)
        def new_cb(*args, **kwargs):
            if self._finished or self._aborted:
                async_logger.info('ignoring response because of already finished %s', self)
                return

            try:
                self._dec()
                intermediate_cb(*args, **kwargs)
            except Exception:
                async_logger.error('aborting %s due to unhandled exception in callback', self)
                async_logger.debug('%s done in %.2fms', self, (time.time() - self._start_time) * 1000.)
                self._aborted = True
                raise

            self.try_finish()

        return new_cb

    def add_notification(self):
        self._inc()

        def new_cb(*args, **kwargs):
            self._dec()
            self.try_finish()

        return new_cb

    def add_future(self, future):
        IOLoop.current().add_future(future, self.add_notification())
        return future

    def get_finish_future(self):
        return self._future

    def __str__(self):
        return 'AsyncGroup(name={})'.format(self._name)


def future_fold(future, result_mapper=None, exception_mapper=None):
    """
    Creates a new future with result or exception processed by result_mapper and exception_mapper.

    If result_mapper or exception_mapper raises an exception, it will be set as an exception for the resulting future.
    Any of the mappers can be None — then the result or exception is left as is.
    """

    res_future = Future()

    def _process(func, value):
        try:
            processed = func(value) if func is not None else value
        except Exception as e:
            res_future.set_exception(e)
            return
        res_future.set_result(processed)

    def _on_ready(wrapped_future):
        exception = wrapped_future.exception()
        if exception is not None:
            if not callable(exception_mapper):
                def default_exception_func(error):
                    raise error
                _process(default_exception_func, exception)
            else:
                _process(exception_mapper, exception)
        else:
            _process(result_mapper, future.result())

    IOLoop.current().add_future(future, callback=_on_ready)
    return res_future


def future_map(future, func):
    return future_fold(future, result_mapper=func)


def future_map_exception(future, func):
    return future_fold(future, exception_mapper=func)
