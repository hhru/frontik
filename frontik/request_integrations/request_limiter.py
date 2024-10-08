import logging
from contextlib import contextmanager
from typing import Union

from frontik.app_integrations.statsd import StatsDClient, StatsDClientStub
from frontik.options import options
from frontik.request_integrations.integrations_dto import IntegrationDto

handlers_count_logger = logging.getLogger('handlers_count')


class ActiveHandlersLimit:
    count = 0
    high_watermark_ratio = 0.75

    def __init__(self, statsd_client: Union[StatsDClient, StatsDClientStub]) -> None:
        self.acquired = False
        self._statsd_client = statsd_client
        self._high_watermark = int(options.max_active_handlers * self.high_watermark_ratio)

        if ActiveHandlersLimit.count > options.max_active_handlers:
            handlers_count_logger.warning('dropping request: too many active handlers (%s)', ActiveHandlersLimit.count)
            return

        elif ActiveHandlersLimit.count > self._high_watermark:
            handlers_count_logger.warning(
                'active handlers count reached %.2f * %s watermark (%s)',
                self.high_watermark_ratio,
                options.max_active_handlers,
                ActiveHandlersLimit.count,
            )

        self.acquire()

    def acquire(self) -> None:
        if not self.acquired:
            ActiveHandlersLimit.count += 1
            self.acquired = True
            self._statsd_client.gauge('handler.active_count', ActiveHandlersLimit.count)

    def release(self) -> None:
        if self.acquired:
            ActiveHandlersLimit.count -= 1
            self.acquired = False
            self._statsd_client.gauge('handler.active_count', ActiveHandlersLimit.count)


@contextmanager
def request_limiter(frontik_app, _):
    active_limit = ActiveHandlersLimit(frontik_app.statsd_client)
    dto = IntegrationDto(active_limit.acquired)
    try:
        yield dto
    finally:
        active_limit.release()