from __future__ import annotations

import asyncio
import logging
import time
from functools import partial, wraps
from typing import TYPE_CHECKING

from tornado.concurrent import Future
from tornado.ioloop import IOLoop

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

async_logger = logging.getLogger('frontik.futures')


class AbortAsyncGroup(Exception):
    pass


# AsyncGroup will become legacy in future releases
# It will be replaced with FutureGroup
class AsyncGroup:
    """
    Grouping of several async requests and final callback in such way that final callback is invoked
    after the last request is finished.

    If any callback throws an exception, all pending callbacks would be aborted and finish_cb
    would not be automatically called.
    """

    def __init__(self, finish_cb: Callable, name: str | None = None) -> None:
        self._counter = 0
        self._finish_cb = finish_cb
        self._finished = False
        self._name = name
        self._future: Future = Future()
        self._start_time = time.time()
        self._futures: list[Future] = []

    def is_finished(self) -> bool:
        return self._finished

    def abort(self) -> None:
        async_logger.info('aborting %s', self)
        self._finished = True
        if not self._future.done():
            self._future.set_exception(AbortAsyncGroup())

    def finish(self) -> None:
        if self._finished:
            async_logger.warning('trying to finish already finished %s', self)
            return None

        self._finished = True
        self._future.set_result(None)

        try:
            self._finish_cb()
        finally:
            # prevent possible cycle references
            self._finish_cb = None  # type: ignore

        return None

    def try_finish(self) -> None:
        if self._counter == 0:
            self.finish()

    def try_finish_async(self):
        """Executes finish_cb in next IOLoop iteration"""
        if self._counter == 0:
            IOLoop.current().add_callback(self.finish)

    def _inc(self) -> None:
        if self._finished:
            async_logger.info('ignoring adding callback in %s', self)
            raise AbortAsyncGroup

        self._counter += 1

    def _dec(self) -> None:
        self._counter -= 1

    def add(self, intermediate_cb: Callable, exception_handler: Callable | None = None) -> Callable:
        self._inc()

        @wraps(intermediate_cb)
        def new_cb(*args, **kwargs):
            if self._finished:
                async_logger.info('ignoring executing callback in %s', self)
                return

            try:
                self._dec()
                intermediate_cb(*args, **kwargs)
            except Exception as ex:
                self.abort()
                if exception_handler is not None:
                    exception_handler(ex)
                else:
                    raise

            self.try_finish()

        return new_cb

    def add_notification(self) -> Callable:
        self._inc()

        def new_cb(*args, **kwargs):
            self._dec()
            self.try_finish()

        return new_cb

    @staticmethod
    def _handle_future(callback, future):
        future.result()
        callback()

    def add_future(self, future: Future) -> Future:
        IOLoop.current().add_future(future, partial(self._handle_future, self.add_notification()))
        self._futures.append(future)
        return future

    def get_finish_future(self) -> Future:
        return self._future

    def get_gathering_future(self) -> Future:
        return asyncio.gather(*self._futures)

    def __str__(self):
        return f'AsyncGroup(name={self._name}, finished={self._finished})'


def future_fold(
    future: Future,
    result_mapper: Callable | None = None,
    exception_mapper: Callable | None = None,
) -> Future:
    """
    Creates a new future with result or exception processed by result_mapper and exception_mapper.

    If result_mapper or exception_mapper raises an exception, it will be set as an exception for the resulting future.
    Any of the mappers can be None — then the result or exception is left as is.
    """

    res_future: Future = Future()

    def _process(func: Callable | None, value: Any) -> None:
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
