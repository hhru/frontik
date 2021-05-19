import time
from typing import Callable, Mapping, AnyStr, Any

from tornado.web import RequestHandler


class TimingsLoggerFactory:

    def __init__(self,
                 handler: RequestHandler,
                 tags_factory: Callable[[RequestHandler], Mapping[AnyStr, Any]]):
        self.handler = handler
        self.tags_factory = tags_factory

    def create_logger(self, metric_name):
        return TimingsLogger(metric_name, self.handler, **self.tags_factory(self.handler))


class TimingsLogger:

    def __init__(self, metric_name: str, handler: RequestHandler, **tags):
        self._metric_name = metric_name
        self._handler = handler
        self._start_time = time.time()
        self.tags = tags

    def commit_time(self, **tags):
        delta = int((time.time() - self._start_time) * 1000)
        all_tags = {
            **self.tags,
            **tags
        }
        self._handler.statsd_client.time(self._metric_name, delta, **all_tags)
