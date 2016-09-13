# coding=utf-8

from collections import namedtuple
import logging
import time

logger = logging.getLogger('frontik.handler')


class ContextFilter(logging.Filter):
    def filter(self, record):
        handler_name = getattr(record, 'handler_name', None)
        request_id = getattr(record, 'request_id', None)
        record.name = '.'.join(filter(None, [record.name, handler_name, request_id]))
        return True

logger.addFilter(ContextFilter())


class ProxyLogger(logging.Logger):
    """
    Proxies everything to "frontik.handler" logger, but allows to add additional per-request handlers
    """

    def handle(self, record):
        logger.handle(record)
        if self.handlers:
            super(ProxyLogger, self).handle(record)


class RequestLogger(logging.LoggerAdapter):

    Stage = namedtuple('Stage', ('name', 'delta', 'start_delta'))

    def __init__(self, request, request_id):
        self._page_handler_name = None
        self._last_stage_time = self._start_time = request._start_time
        self._handlers = []
        self.stages = []

        super(RequestLogger, self).__init__(ProxyLogger('frontik.handler'), {'request_id': request_id})

        # backcompatibility with logger
        self.warn = self.warning
        self.addHandler = self.logger.addHandler

    def register_page_handler(self, page_handler):
        self._page_handler_name = repr(page_handler)
        self.extra['handler_name'] = self._page_handler_name

    def stage_tag(self, stage_name):
        stage_end_time = time.time()
        stage_start_time = self._last_stage_time
        self._last_stage_time = stage_end_time

        delta = (stage_end_time - stage_start_time) * 1000
        start_delta = (stage_start_time - self._start_time) * 1000
        stage = RequestLogger.Stage(stage_name, delta, start_delta)

        self.stages.append(stage)
        self.debug('stage "%s" completed in %.2fms', stage.name, stage.delta, extra={'_stage': stage})

    def get_current_total(self):
        return sum(s.delta for s in self.stages)

    def log_stages(self, status_code):
        """Writes available stages, total value and status code"""

        stages_str = ' '.join('{s.name}={s.delta:.2f}'.format(s=s) for s in self.stages)
        total = sum(s.delta for s in self.stages)

        self.info(
            'timings for %(page)s : %(stages)s',
            {
                'page': self._page_handler_name,
                'stages': '{0} total={1:.2f} code={2}'.format(stages_str, total, status_code)
            },
        )

    def process(self, msg, kwargs):
        if 'extra' in kwargs:
            kwargs['extra'].update(self.extra)
        else:
            kwargs['extra'] = self.extra

        return msg, kwargs
