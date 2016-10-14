# -*- coding: utf-8 -*-

import time
import logging

from tornado.ioloop import IOLoop
from tornado.concurrent import Future

default_logger = logging.getLogger('frontik.async')


class AsyncGroup(object):
    """
    Grouping of several async requests and final callback in such way that final callback is invoked
    after the last request is finished.

    If any callback throws an exception, all pending callbacks would be aborted and finish_cb
    would not be automatically called.
    """

    def __init__(self, finish_cb, log=default_logger.debug, name=None, logger=None):
        self._counter = 0
        self._finish_cb = finish_cb
        self._finish_cb_called = False
        self._aborted = False
        self._logger = logger if logger is not None else default_logger
        self._name = name

        self._start_time = time.time()

        if self._name is not None:
            self._log_name = '{0} group'.format(self._name)
        else:
            self._log_name = 'group'

    def _message(self, message):
        return self._log_name + ': ' + message

    def abort(self):
        self._logger.info(self._message('aborting async group'))
        self._aborted = True

    def finish(self):
        if not self._finish_cb_called:
            self._logger.debug(self._message('done in %.2fms'), (time.time() - self._start_time) * 1000.)
            self._finish_cb_called = True

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
            IOLoop.instance().add_callback(self.finish)

    def _inc(self):
        assert not self._finish_cb_called
        self._counter += 1

    def _dec(self):
        self._counter -= 1
        self._logger.debug(self._message('%s requests pending'), self._counter)

    def add(self, intermediate_cb):
        self._inc()

        def new_cb(*args, **kwargs):
            if not self._finish_cb_called and not self._aborted:
                try:
                    self._dec()
                    intermediate_cb(*args, **kwargs)
                except Exception:
                    self._logger.error(self._message('aborting async group due to unhandled exception in callback'))
                    self._logger.debug(self._message('done in %.2fms'), (time.time() - self._start_time) * 1000.)
                    self._aborted = True
                    raise

                self.try_finish()
            else:
                self._logger.info(self._message('ignoring response because of already finished group'))

        return new_cb

    def add_notification(self):
        self._inc()

        def new_cb(*args, **kwargs):
            self._dec()
            self.try_finish()

        return new_cb


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
