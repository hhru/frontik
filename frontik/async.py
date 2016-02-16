# coding=utf-8

import time
import logging

from tornado import gen
from tornado.concurrent import Future
from tornado.ioloop import IOLoop

default_logger = logging.getLogger('frontik.async')


def dependency(func_or_deps_list):
    """Create a dependency decorator.

    The function can return a ``Future`` or an arbitrary value (which is ignored).
    The dependency is considered resolved when a ``Future`` returned by it is resolved.

    Usage::
        @dependency
        def get_a():
            future = Future()
            # Do something asynchronously
            return future

        @dependency
        def get_b():
            # Do something
            return None

        class Page(PageHandler):
            @get_a
            @get_b
            # Can also be rewritten as:
            # @dependency([get_a, get_b])
            def get_page(self):
                pass

    When the ``Future`` returned by ``get_a`` is resolved, ``get_b`` is called.
    Finally, after ``get_b`` is executed, ``get_page`` will be called.
    """

    def dependency_decorator(func):
        if callable(func_or_deps_list):
            DependencyChain.register_dependency(func, [func_or_deps_list])
        else:
            for dep in reversed(func_or_deps_list):
                dep(func)

        return func

    if callable(func_or_deps_list):
        dep_name = func_or_deps_list.__name__
    else:
        dep_name = [f.__name__ for f in func_or_deps_list]

    dependency_decorator.func_name = 'dependency_decorator({})'.format(dep_name)

    return dependency_decorator


class DependencyChain(object):
    """Controls execution of functions marked with @dependency decorator.

    ``bound_args`` and ``bound_kwargs`` will be passed to each function as positional and keyword arguments.
    """
    def __init__(self, bound_args=None, bound_kwargs=None):
        self._bound_args = bound_args if bound_args else ()
        self._bound_kwargs = bound_kwargs if bound_kwargs else {}

    @gen.coroutine
    def resolve(self, dependencies):
        """Executes the functions passed in ``dependencies`` argument in consecutive order.

        Each dependency is executed only after all preceding dependencies have been executed.
        Returns a future that is resolved only after all dependencies have been resolved.
        """

        for d in dependencies:
            result = d(*self._bound_args, **self._bound_kwargs)
            if not isinstance(result, Future):
                result_future = Future()
                result_future.set_result(result)
                result = result_future

            yield result

    @staticmethod
    def get_dependencies(func):
        """Returns immediate dependencies for `func`."""
        return getattr(func, '_dependency_depends_on', [])

    @staticmethod
    def register_dependency(func, dependencies):
        """Adds dependencies for `func`."""
        setattr(func, '_dependency_depends_on', dependencies + DependencyChain.get_dependencies(func))


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
