import gc
import logging
import time
from functools import partial

from tornado.ioloop import PeriodicCallback
from tornado.options import options

metrics_logger = logging.getLogger('frontik.loggers.metrics')


def bootstrap_logger(app):
    if options.generic_metrics_send_interval_ms is None or options.generic_metrics_send_interval_ms <= 0:
        return lambda *args: None

    gc.callbacks.append(gc_callback)

    periodic_callback = PeriodicCallback(partial(send_metrics, app), options.generic_metrics_send_interval_ms)
    periodic_callback.start()

    return lambda *args: None


class GCStats:
    __slots__ = ('start', 'duration', 'count')

    def __init__(self):
        self.start = None
        self.duration = 0
        self.count = 0


GC_STATS = GCStats()


def gc_callback(phase, info):
    if phase == 'start':
        GC_STATS.start = time.time()
    elif phase == 'stop' and GC_STATS.start is not None:
        GC_STATS.duration += time.time() - GC_STATS.start
        GC_STATS.count += 1


def send_metrics(app):
    if GC_STATS.count == 0:
        app.statsd_client.time('gc.duration', 0)
        app.statsd_client.count('gc.count', 0)
    else:
        app.statsd_client.time('gc.duration', int(GC_STATS.duration * 1000))
        app.statsd_client.count('gc.count', GC_STATS.count)
        GC_STATS.duration = GC_STATS.count = 0
