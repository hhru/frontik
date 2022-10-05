import gc
import time
from asyncio import Future
from functools import partial
from typing import Optional

from tornado.ioloop import PeriodicCallback

from frontik.integrations import Integration, integrations_logger
from frontik.options import options


class GCMetricsCollectorIntegration(Integration):
    def initialize_app(self, app) -> Optional[Future]:
        if options.gc_metrics_send_interval_ms is None or options.gc_metrics_send_interval_ms <= 0:
            integrations_logger.info(
                'GC metrics collector integration is disabled: gc_metrics_send_interval_ms option is not configured'
            )
            return

        gc.callbacks.append(gc_metrics_collector)

        periodic_callback = PeriodicCallback(partial(send_metrics, app), options.gc_metrics_send_interval_ms)
        periodic_callback.start()

    def initialize_handler(self, handler):
        pass


class GCStats:
    __slots__ = ('start', 'duration', 'count', 'max_stw')

    def __init__(self):
        self.start = None
        self.duration = 0
        self.count = 0
        self.max_stw = 0

    def on_gc_start(self):
        self.start = time.perf_counter()

    def on_gc_stop(self):
        gc_duration = time.perf_counter() - self.start
        self.duration += gc_duration
        self.count += 1
        self.max_stw = max(self.max_stw, gc_duration)

    def clear(self):
        self.duration = 0
        self.count = 0
        self.max_stw = 0


GC_STATS = GCStats()


def gc_metrics_collector(phase, info):
    if phase == 'start':
        GC_STATS.on_gc_start()
    elif phase == 'stop' and GC_STATS.start is not None:
        GC_STATS.on_gc_stop()


def send_metrics(app):
    if GC_STATS.count == 0:
        app.statsd_client.time('gc.duration', 0)
        app.statsd_client.count('gc.count', 0)
        app.statsd_client.gauge('gc.max_duration_ms', 0)
    else:
        app.statsd_client.time('gc.duration', int(GC_STATS.duration * 1000))
        app.statsd_client.count('gc.count', GC_STATS.count)
        app.statsd_client.gauge('gc.max_duration_ms', int(GC_STATS.max_stw * 1000))
        GC_STATS.clear()
