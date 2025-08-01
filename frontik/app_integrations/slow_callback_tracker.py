import asyncio
import gc
import logging
import sys
import time
from asyncio import Future
from functools import partial
from typing import Optional

import sentry_sdk

from frontik.app import FrontikApplication
from frontik.app_integrations import Integration, integrations_logger
from frontik.loggers import bootstrap_logger
from frontik.options import options

current_callback_start = None
py_ver = sys.version_info[1]


class SlowCallbackTrackerIntegration(Integration):
    def initialize_app(self, app: FrontikApplication) -> Optional[Future]:
        if options.asyncio_task_threshold_sec is None:
            integrations_logger.info(
                'slow callback tracker integration is disabled: asyncio_task_threshold_sec option is None',
            )
            return None
        slow_tasks_logger = bootstrap_logger('slow_tasks', logging.WARNING)
        import reprlib

        reprlib.aRepr.maxother = 256
        wrap_handle_with_time_logging(app, slow_tasks_logger)
        gc.callbacks.append(long_gc_tracker)

        return None


def wrap_handle_with_time_logging(app: FrontikApplication, slow_tasks_logger: logging.Logger) -> None:
    old_run = asyncio.Handle._run

    def _log_slow_tasks(handle: asyncio.Handle, delta: float) -> None:
        delta_ms = delta * 1000
        app.statsd_client.time('long_task.time', int(delta_ms))
        slow_tasks_logger.warning('%s took %.2fms', handle, delta_ms)

        if (
            options.asyncio_task_critical_threshold_sec
            and delta >= options.asyncio_task_critical_threshold_sec
            and options.sentry_dsn
        ):
            sentry_sdk.capture_message(f'{handle} took {delta_ms:.2f} ms', level='error')

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

    asyncio.Handle._run = run  # type: ignore


class GCStats:
    __slots__ = ('callback_start', 'gc_start', 'sum_duration')

    def __init__(self) -> None:
        self.callback_start: Optional[float] = None
        self.gc_start: Optional[float] = None
        self.sum_duration: float = 0


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
