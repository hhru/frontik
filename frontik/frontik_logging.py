# coding=utf-8

import logging
import time
import socket
from collections import namedtuple
from functools import partial
from logging.handlers import SysLogHandler, WatchedFileHandler

import tornado.options
from tornado.options import options


log = logging.getLogger('frontik.handler')


class ContextFilter(logging.Filter):
    def filter(self, record):
        handler = getattr(record, 'handler', None)
        handler_id = repr(handler) if handler is not None else None
        request_id = getattr(record, 'request_id', None)
        record.name = '.'.join(filter(None, [record.name, handler_id, request_id]))
        return True

log.addFilter(ContextFilter())


class PerRequestLogBufferHandler(logging.Logger):
    """
    Handler for storing all LogRecords for current request in a buffer until finish
    """
    def __init__(self, name, level=logging.NOTSET):
        super(PerRequestLogBufferHandler, self).__init__(name, level)
        self.records_list = []
        self.bulk_handlers = []

    def handle(self, record):
        log.handle(record)
        self.records_list.append(record)

    def add_bulk_handler(self, handler, auto_flush=True):
        self.bulk_handlers.append((handler, auto_flush))
        if not auto_flush:
            handler.flush = partial(self.flush_bulk_handler, handler)

    def flush_bulk_handler(self, handler, **kwargs):
        handler.handle_bulk(self.records_list, **kwargs)

    def flush(self, **kwargs):
        for handler, auto_flush in self.bulk_handlers:
            if auto_flush:
                self.flush_bulk_handler(handler, **kwargs)


class RequestLogger(logging.LoggerAdapter):

    Stage = namedtuple('Stage', ('name', 'delta', 'start_delta'))

    def __init__(self, request, request_id):
        self._handler = None
        self._last_stage_time = self._start_time = request._start_time

        super(RequestLogger, self).__init__(PerRequestLogBufferHandler('frontik.handler'), {'request_id': request_id})

        self.stages = []

        # backcompatibility with logger
        self.warn = self.warning
        self.addHandler = self.logger.addHandler

    def register_handler(self, handler):
        self._handler = handler
        self.extra['handler'] = handler

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
                'page': repr(self._handler),
                'stages': '{0} total={1:.2f} code={2}'.format(stages_str, total, status_code)
            },
        )

    def process(self, msg, kwargs):
        if 'extra' in kwargs:
            kwargs['extra'].update(self.extra)
        else:
            kwargs['extra'] = self.extra
        return msg, kwargs

    def add_bulk_handler(self, handler, auto_flush=True):
        self.logger.add_bulk_handler(handler, auto_flush)

    def request_finish_hook(self, status_code, request_method, request_uri):
        self.logger.flush(status_code=status_code, stages=self.stages, method=request_method, uri=request_uri)


def bootstrap_logging():
    """This is a replacement for standard Tornado logging configuration."""

    root_logger = logging.getLogger()
    level = getattr(logging, options.loglevel.upper())
    root_logger.setLevel(logging.NOTSET)

    if options.logfile:
        handler = logging.handlers.WatchedFileHandler(options.logfile)
        handler.setFormatter(logging.Formatter(options.logformat))
        handler.setLevel(level)
        root_logger.addHandler(handler)

    if options.stderr_log:
        if hasattr(tornado.options, 'enable_pretty_logging'):
            # Old Tornado version
            tornado.options.enable_pretty_logging(level)

        else:
            from tornado.log import LogFormatter

            handler = logging.StreamHandler()
            handler.setFormatter(
                LogFormatter(
                    fmt=tornado.options.options.stderr_format, datefmt=tornado.options.options.stderr_dateformat
                )
            )

            handler.setLevel(level)
            root_logger.addHandler(handler)

    if options.syslog:
        if options.syslog_port is not None:
            syslog_address = (options.syslog_address, options.syslog_port)
        else:
            syslog_address = options.syslog_address

        try:
            syslog_handler = SysLogHandler(
                facility=SysLogHandler.facility_names[options.syslog_facility],
                address=syslog_address
            )
            syslog_handler.setFormatter(logging.Formatter(options.logformat))
            syslog_handler.setLevel(level)
            root_logger.addHandler(syslog_handler)
        except socket.error:
            logging.getLogger('frontik.logging').exception('cannot initialize syslog')

    for logger_name in options.suppressed_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARN)
