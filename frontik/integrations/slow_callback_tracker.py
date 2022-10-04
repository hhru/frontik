import asyncio
import gc
import logging
import time
from asyncio import Future
from functools import partial
from typing import Optional

from tornado.httputil import HTTPServerRequest

from frontik.app import FrontikApplication
from frontik.integrations import Integration, integrations_logger
from frontik.loggers import bootstrap_logger
from frontik.options import options
from frontik.request_context import get_request

current_callback_start = None
long_gc_log = None


class SlowCallbackTrackerIntegration(Integration):
    def initialize_app(self, app) -> Optional[Future]:
        if options.asyncio_task_threshold_sec is None:
            integrations_logger.info(
                'slow callback tracker integration is disabled: asyncio_task_threshold_sec option is None'
            )
            return
        slow_tasks_logger = bootstrap_logger('slow_tasks', logging.WARNING)
        import reprlib

        reprlib.aRepr.maxother = 256
        wrap_handle_with_time_logging(app, slow_tasks_logger)
        gc.callbacks.append(long_gc_tracker)

        if options.long_gc_log_enabled:
            global long_gc_log
            long_gc_log = bootstrap_logger('gc_stat', logging.WARNING)

    def initialize_handler(self, handler):
        pass


def wrap_handle_with_time_logging(app: FrontikApplication, slow_tasks_logger):
    old_run = asyncio.Handle._run

    def _log_slow_tasks(handle: asyncio.Handle, delta: float):
        delta_ms = delta * 1000
        app.statsd_client.time('long_task.time', int(delta_ms))
        slow_tasks_logger.warning('%s took %.2fms', handle, delta_ms)

        if options.asyncio_task_critical_threshold_sec and delta >= options.asyncio_task_critical_threshold_sec:
            request = get_request() or HTTPServerRequest('GET', '/asyncio_long_task_stub')
            sentry_logger = app.get_sentry_logger(request)
            sentry_logger.update_user_info(ip='127.0.0.1')

            if sentry_logger:
                slow_tasks_logger.warning('no sentry logger available')
                sentry_logger.capture_message(f'{handle} took {delta_ms:.2f} ms', stack=True)

    def run(self):
        global current_callback_start
        current_callback_start = time.time()

        start_time = self._loop.time()
        old_run(self)
        delta = self._loop.time() - start_time

        gc_duration = GC_STATS.sum_duration
        GC_STATS.sum_duration = 0
        current_callback_start = None
        delta -= gc_duration

        if delta >= options.asyncio_task_threshold_sec:
            self._context.run(partial(_log_slow_tasks, self, delta))

    asyncio.Handle._run = run


class GCStats:
    __slots__ = ('callback_start', 'gc_start', 'sum_duration')

    def __init__(self):
        self.callback_start = None
        self.gc_start = None
        self.sum_duration = 0


GC_STATS = GCStats()


def long_gc_tracker(phase, info):
    if current_callback_start is None:
        return

    if phase == 'start':
        GC_STATS.gc_start = time.time()
    elif phase == 'stop' and GC_STATS.gc_start is not None:
        gc_end_time = time.time()
        gc_duration = gc_end_time - GC_STATS.gc_start

        if current_callback_start == GC_STATS.callback_start:
            GC_STATS.sum_duration += gc_duration
        elif current_callback_start != GC_STATS.callback_start:
            GC_STATS.callback_start = current_callback_start
            GC_STATS.sum_duration = gc_duration

        if long_gc_log is not None and gc_duration > options.long_gc_log_threshold_sec:
            long_gc_log.warning(f'GC took {gc_duration*1000} ms')
