from __future__ import annotations

import logging
from collections import namedtuple
from functools import partial
from typing import TYPE_CHECKING, Optional

from tornado.ioloop import PeriodicCallback

from frontik.options import options
from frontik.request_context import get_handler_name

if TYPE_CHECKING:
    from collections.abc import Callable

    from http_client.request_response import RequestBuilder


timeout_tracking_logger = logging.getLogger('timeout_tracking')
LoggingData = namedtuple(
    'LoggingData',
    ('outer_caller', 'outer_timeout_ms', 'upstream', 'handler_name', 'request_timeout_ms'),
)


class TimeoutCounter(dict):
    def increment(self, k: LoggingData, already_spent_ms: float) -> None:
        count, max_already_spent_ms = super().__getitem__(k)
        super().__setitem__(k, (count + 1, max(already_spent_ms, max_already_spent_ms)))

    def __missing__(self, key):
        return 0, 0


class Sender:
    def __init__(self) -> None:
        self._timeout_counters = TimeoutCounter()
        self._send_stats_callback: Optional[PeriodicCallback] = None

    def send_data(self, data: LoggingData, already_spent_ms: float) -> None:
        self._timeout_counters.increment(data, already_spent_ms)

    @property
    def send_stats_callback(self):
        if not hasattr(self, '_send_stats_callback'):
            if options.send_timeout_stats_interval_ms:
                self._send_stats_callback = PeriodicCallback(
                    partial(self.__send_aggregated_stats, options.send_timeout_stats_interval_ms),
                    options.send_timeout_stats_interval_ms,
                )
            else:
                self._send_stats_callback = None
        return self._send_stats_callback

    def start_sending_if_needed(self) -> None:
        if self.send_stats_callback and not self.send_stats_callback.is_running():
            self.send_stats_callback.start()

    def __send_aggregated_stats(self, interval_ms):
        timeout_tracking_logger.debug('timeout stats size: %d', len(self._timeout_counters))
        for data, counters in self._timeout_counters.items():
            count, max_already_spent_ms = counters
            timeout_tracking_logger.error(
                'For last %d ms, got %d requests from <%s> expecting timeout=%d ms, '
                'but calling upstream <%s> from handler <%s> with timeout %d ms, '
                'arbitrary we spend up to %d ms before the call',
                interval_ms,
                count,
                data.outer_caller,
                data.outer_timeout_ms,
                data.upstream,
                data.handler_name,
                data.request_timeout_ms,
                max_already_spent_ms,
            )
        self._timeout_counters.clear()


_sender = Sender()


class TimeoutChecker:
    def __init__(
        self,
        outer_caller: Optional[str],
        outer_timeout_ms: float,
        time_since_outer_request_start_sec_supplier: Callable,
        *,
        threshold_ms: float = 100,
    ) -> None:
        self.outer_caller = outer_caller
        self.outer_timeout_ms = outer_timeout_ms
        self.time_since_outer_request_start_sec_supplier = time_since_outer_request_start_sec_supplier
        self.threshold_ms = threshold_ms

    def check(self, request: RequestBuilder) -> None:
        if self.outer_timeout_ms:
            already_spent_time_ms = self.time_since_outer_request_start_sec_supplier() * 1000
            expected_timeout_ms = self.outer_timeout_ms - already_spent_time_ms
            request_timeout_ms = request.request_time_left * 1000
            diff = request_timeout_ms - expected_timeout_ms
            if diff > self.threshold_ms:
                data = LoggingData(
                    self.outer_caller,
                    self.outer_timeout_ms,
                    request.upstream_name,
                    get_handler_name(),
                    request_timeout_ms,
                )
                _sender.send_data(data, already_spent_time_ms)


def get_timeout_checker(
    outer_caller: Optional[str],
    outer_timeout_ms: float,
    time_since_outer_request_start_ms_supplier: Callable,
    *,
    threshold_ms: float = 100,
) -> TimeoutChecker:
    _sender.start_sending_if_needed()
    return TimeoutChecker(
        outer_caller,
        outer_timeout_ms,
        time_since_outer_request_start_ms_supplier,
        threshold_ms=threshold_ms,
    )
