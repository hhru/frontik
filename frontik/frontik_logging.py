# coding=utf-8

from collections import namedtuple
import copy
from functools import partial
import logging
import traceback
import weakref
import time
import socket
from logging.handlers import SysLogHandler, WatchedFileHandler

import tornado.options
from tornado.escape import to_unicode
from lxml.builder import E

try:
    import frontik.options
    from graypy.handler import GELFHandler, LAN_CHUNK

    class BulkGELFHandler(GELFHandler):
        @staticmethod
        def format_time(record):
            t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created))
            return "%s,%03d" % (t, record.msecs)

        def handle_bulk(self, records_list, stages=None, status_code=None, uri=None, method=None, **kwargs):
            if len(records_list) > 0:
                first_record = records_list[0]
            else:
                return

            record_for_gelf = copy.deepcopy(first_record)
            record_for_gelf.message = ''
            record_for_gelf.exc_info = ''
            record_for_gelf.short = u"{0} {1} {2}".format(method, to_unicode(uri), status_code)
            record_for_gelf.levelno = logging.INFO
            record_for_gelf.name = record_for_gelf.handler
            record_for_gelf.code = status_code

            for record in records_list:
                message = to_unicode(record.getMessage())
                if record.levelno > record_for_gelf.levelno:
                    record_for_gelf.levelno = record.levelno
                    record_for_gelf.lineno = record.lineno
                    record_for_gelf.short = message
                if record.exc_info is not None:
                    exception_text = '\n' + ''.join(traceback.format_exception(*record.exc_info))
                    record_for_gelf.exc_info += exception_text
                    record_for_gelf.short += exception_text

                record_for_gelf.message += u' {0} {1} {2} \n'.format(
                    self.format_time(record), record.levelname, message)

            if stages is not None:
                for stage_name, stage_delta in stages:
                    setattr(record_for_gelf, stage_name + '_stage', str(int(stage_delta)))

            GELFHandler.handle(self, record_for_gelf)
            GELFHandler.close(self)

except ImportError:
    import frontik.options
    tornado.options.options.graylog = False

log = logging.getLogger('frontik.handler')


class ContextFilter(logging.Filter):
    def filter(self, record):
        record.name = '.'.join(filter(None, [record.name, getattr(record, 'request_id', None)]))
        return True

log.addFilter(ContextFilter())


class MonikInfoLoggingFilter(logging.Filter):
    def filter(self, record):
        return getattr(record, '_monik', False)


class MonikInfoLoggingHandler(WatchedFileHandler):
    def __init__(self):
        WatchedFileHandler.__init__(self, self.__get_logfile_name())
        self.setLevel(logging.INFO)
        self.addFilter(MonikInfoLoggingFilter())
        self.setFormatter(logging.Formatter(tornado.options.options.logformat))

    def __get_logfile_name(self):
        logfile_parts = tornado.options.options.logfile.rsplit('.', 1)
        logfile_parts.insert(1, 'monik')
        return '.'.join(logfile_parts)


class MaxLenSysLogHandler(SysLogHandler):
    """
    Extension of standard SysLogHandler with possibility to limit log message sizes
    """

    MIN_MSG_LENGTH_LIMIT = 100
    STD_MSG_LENGTH_LIMIT = 2048

    def __init__(self, msg_max_length=STD_MSG_LENGTH_LIMIT, *args, **kwargs):
        if msg_max_length >= self.MIN_MSG_LENGTH_LIMIT:
            self.max_length = msg_max_length
        else:
            self.max_length = self.STD_MSG_LENGTH_LIMIT
        SysLogHandler.__init__(self, *args, **kwargs)

    def format(self, record):
        """
        prio_length is length of '<prio>' header which is attached to message before sending to syslog
        so we need to subtract it from max_length to guarantee that length of resulting message
        won't be greater than max_length
        """
        prio_length = len('%d' % self.encodePriority(self.facility, self.mapPriority(record.levelname))) + 2  # 2 is length of angle brackets
        return SysLogHandler.format(self, record)[:(self.max_length - prio_length)]


class PerRequestLogBufferHandler(logging.Logger):
    """
    Handler for storing all LogRecords for current request in a buffer until finish
    """
    def __init__(self, name, level=logging.NOTSET):
        logging.Logger.__init__(self, name, level)
        self.records_list = []
        self.bulk_handlers = []

    def handle(self, record):
        logging.Logger.handle(self, record)
        log.handle(record)
        if len(self.bulk_handlers) > 0:
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


class PageLogger(logging.LoggerAdapter):

    Stage = namedtuple('Stage', ['name', 'delta'])

    def __init__(self, handler, logger_name, page):
        self.handler_ref = weakref.ref(handler)
        self.handler_started = self.handler_ref().handler_started
        logging.LoggerAdapter.__init__(self, PerRequestLogBufferHandler('frontik.handler'),
                                       dict(request_id=logger_name, page=page, handler=self.handler_ref().__module__))

        self._time = self.handler_started
        self.stages = []
        self.page = page
        # backcompatibility with logger
        self.warn = self.warning
        self.addHandler = self.logger.addHandler

        if tornado.options.options.graylog:
            self.logger.add_bulk_handler(BulkGELFHandler(tornado.options.options.graylog_host,
                                                         tornado.options.options.graylog_port, LAN_CHUNK, False))

    def stage_tag(self, stage_name):
        self._stage_tag(PageLogger.Stage(stage_name, (time.time() - self._time) * 1000))
        self._time = time.time()
        self.debug('Stage: {stage}'.format(stage=stage_name))

    def _stage_tag(self, stage):
        self.stages.append(stage)

    def process_stages(self, status_code):
        self._stage_tag(PageLogger.Stage('total', (time.time() - self.handler_started) * 1000))

        format_f = lambda x: ' '.join([x.format(name=s.name, delta=s.delta) for s in self.stages])
        stages_format = format_f('{name}:{delta:.2f}ms')
        stages_monik_format = format_f('{name}={delta:.2f}')

        self.debug('Stages for {0} : {1}'.format(self.page, stages_format))
        self.info('Monik-stages {0!r} : {1} code={2}'.format(self.handler_ref(), stages_monik_format, status_code),
                  extra={
                      '_monik': True,
                      '_stages': E.stages(*[E.stage(str(s.delta), {'name': str(s.name)}) for s in self.stages])
                  })

    def process(self, msg, kwargs):
        if "extra" in kwargs:
            kwargs["extra"].update(self.extra)
        else:
            kwargs["extra"] = self.extra
        return msg, kwargs

    def add_bulk_handler(self, handler, auto_flush=True):
        self.logger.add_bulk_handler(handler, auto_flush)

    def request_finish_hook(self, status_code, request_method, request_uri):
        self.logger.flush(status_code=status_code, stages=self.stages, method=request_method, uri=request_uri)


def bootstrap_logging():
    root_logger = logging.getLogger()
    level = getattr(logging, tornado.options.options.loglevel.upper())

    if tornado.options.options.logfile:
        handler = logging.handlers.WatchedFileHandler(tornado.options.options.logfile)
        handler.setFormatter(logging.Formatter(tornado.options.options.logformat))
        handler.setLevel(level)
        root_logger.setLevel(logging.NOTSET)
        root_logger.addHandler(handler)
    else:
        root_logger.setLevel(level)
        tornado.options.enable_pretty_logging()  # TODO: replace it with LogFormatter from Tornado 3

    if tornado.options.options.syslog:
        try:
            syslog_handler = MaxLenSysLogHandler(
                facility=MaxLenSysLogHandler.facility_names[tornado.options.options.syslog_facility],
                address=tornado.options.options.syslog_address,
                msg_max_length=tornado.options.options.syslog_msg_max_length
            )
            syslog_handler.setFormatter(logging.Formatter(tornado.options.options.logformat))
            root_logger.addHandler(syslog_handler)
        except socket.error:
            logging.getLogger('frontik.logging').exception('Cannot initialize syslog')

    if tornado.options.options.logfile is not None:
        root_logger.addHandler(MonikInfoLoggingHandler())

    for log_channel_name in tornado.options.options.suppressed_loggers:
        logging.getLogger(log_channel_name).setLevel(logging.WARN)
