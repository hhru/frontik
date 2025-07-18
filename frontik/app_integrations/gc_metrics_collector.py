from __future__ import annotations

import gc
import logging
import time
from functools import partial
from logging import Logger
from typing import TYPE_CHECKING, Optional

from tornado.ioloop import PeriodicCallback

from frontik.app_integrations import Integration, integrations_logger
from frontik.loggers import bootstrap_logger
from frontik.options import options

if TYPE_CHECKING:
    from asyncio import Future

    from frontik.app import FrontikApplication

long_gc_log: Optional[Logger] = None


class GCMetricsCollectorIntegration(Integration):
    def initialize_app(self, app: FrontikApplication) -> Optional[Future]:
        if options.long_gc_log_enabled:
            global long_gc_log
            long_gc_log = bootstrap_logger('gc_stat', logging.WARNING)

        if options.gc_metrics_send_interval_ms is None or options.gc_metrics_send_interval_ms <= 0:
            integrations_logger.info(
                'GC metrics collector integration is disabled: gc_metrics_send_interval_ms option is not configured',
            )
            return None

        gc.callbacks.append(gc_metrics_collector)

        periodic_callback = PeriodicCallback(partial(send_metrics, app), options.gc_metrics_send_interval_ms)
        periodic_callback.start()
        return None


class GCStats:
    __slots__ = ('count', 'duration', 'max_stw', 'start')

    def __init__(self) -> None:
        self.start: float = 0
        self.duration: float = 0
        self.count = 0
        self.max_stw: float = 0

    def on_gc_start(self) -> None:
        self.start = time.perf_counter()

    def on_gc_stop(self) -> None:
        gc_duration = time.perf_counter() - self.start
        self.duration += gc_duration
        self.count += 1
        self.max_stw = max(self.max_stw, gc_duration)

    def clear(self) -> None:
        self.duration = 0
        self.count = 0
        self.max_stw = 0


GC_STATS = GCStats()


def gc_metrics_collector(phase, info):
    if phase == 'start':
        GC_STATS.on_gc_start()
    elif phase == 'stop' and GC_STATS.start is not None:
        GC_STATS.on_gc_stop()

        if long_gc_log is not None and GC_STATS.duration > options.long_gc_log_threshold_sec:
            long_gc_log.debug('GC took %d ms', GC_STATS.duration * 1000)


def send_metrics(app):
    if GC_STATS.count == 0:
        app.statsd_client.time('gc.duration', 0)
        app.statsd_client.count('gc.count', 0)
        app.statsd_client.time('gc.max_duration', 0)
    else:
        app.statsd_client.time('gc.duration', int(GC_STATS.duration * 1000))
        app.statsd_client.count('gc.count', GC_STATS.count)
        app.statsd_client.time('gc.max_duration', int(GC_STATS.max_stw * 1000))
        GC_STATS.clear()
