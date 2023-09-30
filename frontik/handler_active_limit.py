from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tornado.web import HTTPError

from frontik.options import options

if TYPE_CHECKING:
    from frontik.integrations.statsd import StatsDClient, StatsDClientStub

handlers_count_logger = logging.getLogger('handlers_count')


class ActiveHandlersLimit:
    count = 0
    high_watermark_ratio = 0.75

    def __init__(self, statsd_client: StatsDClient | StatsDClientStub) -> None:
        self._acquired = False
        self._statsd_client = statsd_client
        self._high_watermark = int(options.max_active_handlers * self.high_watermark_ratio)

        if ActiveHandlersLimit.count > options.max_active_handlers:
            handlers_count_logger.warning('dropping request: too many active handlers (%s)', ActiveHandlersLimit.count)

            raise HTTPError(503)

        elif ActiveHandlersLimit.count > self._high_watermark:
            handlers_count_logger.warning(
                'active handlers count reached %.2f * %s watermark (%s)',
                self.high_watermark_ratio,
                options.max_active_handlers,
                ActiveHandlersLimit.count,
            )

        self.acquire()

    def acquire(self) -> None:
        if not self._acquired:
            ActiveHandlersLimit.count += 1
            self._acquired = True
            self._statsd_client.gauge('handler.active_count', ActiveHandlersLimit.count)

    def release(self) -> None:
        if self._acquired:
            ActiveHandlersLimit.count -= 1
            self._acquired = False
            self._statsd_client.gauge('handler.active_count', ActiveHandlersLimit.count)
