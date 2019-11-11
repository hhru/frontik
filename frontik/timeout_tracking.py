import logging
from collections import Counter
from frontik.request_context import get_handler_name
from functools import partial
from tornado.ioloop import PeriodicCallback
from tornado.options import options


timeout_tracking_logger = logging.getLogger('timeout_tracking')
_timeout_counters = Counter()


class Sender:
    @property
    def send_stats_callback(self):
        if not hasattr(self, '_send_stats_callback'):
            if options.send_timeout_stats_interval_ms:
                self._send_stats_callback = PeriodicCallback(
                    partial(self.__send_stats, options.send_timeout_stats_interval_ms),
                    options.send_timeout_stats_interval_ms)
            else:
                self._send_stats_callback = None
        return self._send_stats_callback

    @staticmethod
    def __send_stats(interval_ms):
        timeout_tracking_logger.debug('timeout stats size: %d', len(_timeout_counters))
        for data, count in _timeout_counters.items():
            timeout_tracking_logger.error('For last %d ms, got %d requests from <%s> expecting timeout=%d ms, '
                                          'but calling upstream <%s> from handler <%s> with timeout %d ms, '
                                          'arbitrary we spend %d ms before the call',
                                          interval_ms,
                                          count,
                                          data.outer_caller,
                                          data.outer_timeout_ms,
                                          data.upstream,
                                          data.handler,
                                          data.request_timeout_ms,
                                          data.already_spent_time_ms)
        _timeout_counters.clear()


__sender = Sender()


def get_timeout_checker(outer_caller, outer_timeout_ms, time_since_outer_request_start_ms_supplier, *,
                        threshold_ms=100):
    if __sender.send_stats_callback and not __sender.send_stats_callback.is_running():
        __sender.send_stats_callback.start()
    return TimeoutChecker(outer_caller, outer_timeout_ms, time_since_outer_request_start_ms_supplier,
                          threshold_ms=threshold_ms)


class TimeoutChecker:
    def __init__(self, outer_caller, outer_timeout_ms, time_since_outer_request_start_sec_supplier, *,
                 threshold_ms=100):
        self.outer_caller = outer_caller
        self.outer_timeout_ms = outer_timeout_ms
        self.time_since_outer_request_start_sec_supplier = time_since_outer_request_start_sec_supplier
        self.threshold_ms = threshold_ms

    class LoggingData:
        __slots__ = ('outer_caller', 'outer_timeout_ms',
                     'handler', 'upstream', 'request_timeout_ms',
                     'already_spent_time_ms')

        def __init__(self, outer_caller, outer_timeout_ms,
                     handler, upstream, request_timeout_ms,
                     already_spent_time_ms):
            self.outer_caller = outer_caller
            self.outer_timeout_ms = outer_timeout_ms
            self.handler = handler
            self.upstream = upstream
            self.request_timeout_ms = request_timeout_ms
            self.already_spent_time_ms = already_spent_time_ms

        def __hash__(self):
            return hash((self.outer_caller, self.outer_timeout_ms,
                         self.handler, self.upstream, self.request_timeout_ms))

        def __eq__(self, other):
            return self.outer_caller == other.outer_caller \
                   and self.outer_timeout_ms == other.outer_timeout_ms \
                   and self.handler == other.handler \
                   and self.upstream == other.upstream \
                   and self.request_timeout_ms == other.request_timeout_ms

    def check(self, request):
        if self.outer_timeout_ms:
            already_spent_time_ms = self.time_since_outer_request_start_sec_supplier() * 1000
            expected_timeout_ms = self.outer_timeout_ms - already_spent_time_ms
            request_timeout_ms = request.request_time_left * 1000
            diff = request_timeout_ms - expected_timeout_ms
            if diff > self.threshold_ms:
                data = TimeoutChecker.LoggingData(self.outer_caller, self.outer_timeout_ms,
                                                  get_handler_name(),
                                                  request.upstream.name if request.upstream else None,
                                                  request_timeout_ms,
                                                  already_spent_time_ms)
                _timeout_counters[data] += 1
