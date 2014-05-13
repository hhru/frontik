# coding=utf-8

import copy
import logging
import traceback
import weakref
import time
import socket
from collections import namedtuple
from functools import partial
from logging.handlers import SysLogHandler, WatchedFileHandler

import tornado.options
from tornado.escape import to_unicode

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
            record_for_gelf.message = u''
            record_for_gelf.exc_info = None
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

                # only the last exception will be sent in exc_info
                if record.exc_info is not None:
                    exception_text = u'\n' + u''.join(map(to_unicode, traceback.format_exception(*record.exc_info)))
                    record_for_gelf.exc_info = record.exc_info
                    record_for_gelf.short += exception_text

                record_for_gelf.message += u' {time} {level} {msg} \n'.format(
                    time=self.format_time(record), level=record.levelname, msg=message
                )

            if stages is not None:
                for s in stages:
                    setattr(record_for_gelf, s.name + '_stage', str(int(s.delta)))

            GELFHandler.handle(self, record_for_gelf)
            GELFHandler.close(self)

except ImportError:
    import frontik.options
    tornado.options.options.graylog = False

log = logging.getLogger('frontik.handler')
timings_log = logging.getLogger('frontik.timings')


class ContextFilter(logging.Filter):
    def filter(self, record):
        record.name = '.'.join(filter(None, [record.name, getattr(record, 'request_id', None)]))
        return True

log.addFilter(ContextFilter())
timings_log.addFilter(ContextFilter())


class TimingsLoggingHandler(WatchedFileHandler):
    def __init__(self):
        WatchedFileHandler.__init__(self, self.__get_logfile_name())
        self.setLevel(logging.INFO)
        self.setFormatter(logging.Formatter(tornado.options.options.logformat))

    @staticmethod
    def __get_logfile_name():
        logfile_parts = tornado.options.options.logfile.rsplit('.', 1)
        logfile_parts.insert(1, tornado.options.options.timings_log_file_postfix)
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
        prio_length = len('%d' % self.encodePriority(self.facility, self.mapPriority(record.levelname))) + len('<>')
        return SysLogHandler.format(self, record)[:(self.max_length - prio_length)]


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

    Stage = namedtuple('Stage', ('name', 'delta', 'start_delta'))

    def __init__(self, handler, logger_name, page):
        self._handler_ref = weakref.ref(handler)
        self._handler_started = self._handler_ref().handler_started
        super(PageLogger, self).__init__(
            PerRequestLogBufferHandler('frontik.handler'),
            dict(request_id=logger_name, page=page, handler=self._handler_ref().__module__)
        )

        self._time = self._handler_started
        self._page = page
        self.stages = []

        # backcompatibility with logger
        self.warn = self.warning
        self.addHandler = self.logger.addHandler

        if tornado.options.options.graylog:
            self.logger.add_bulk_handler(BulkGELFHandler(tornado.options.options.graylog_host,
                                                         tornado.options.options.graylog_port, LAN_CHUNK, False))

    def stage_tag(self, stage_name):
        end_time = time.time()
        start_time = self._time
        self._time = end_time

        delta = (end_time - start_time) * 1000
        start_delta = (start_time - self._handler_started) * 1000
        stage = PageLogger.Stage(stage_name, delta, start_delta)

        self.stages.append(stage)
        self.debug('stage "%s" completed in %.2fms', stage.name, stage.delta, extra={'_stage': stage._asdict()})

    def log_stages(self):
        """Writes available stages and total value to page logger"""

        stages_str = ', '.join('{0}={1:.2f}'.format(s.name, s.delta) for s in self.stages)
        current_total = sum(s.delta for s in self.stages)

        self.info('Stages: %s, total=%.2f', stages_str, current_total, extra={
            '_stages': [(s.name, s.delta) for s in self.stages] + [('total', current_total)]
        })

    def finish_stages(self, status_code):
        """Writes available stages and total value to timings logger"""

        stages_str = ' '.join('{s.name}={s.delta:.2f}'.format(s=s) for s in self.stages)
        total = sum(s.delta for s in self.stages)

        timings_log.info(
            tornado.options.options.timings_log_message_format,
            {
                'page': repr(self._handler_ref()),
                'stages': '{0} total={1:.2f} code={2}'.format(stages_str, total, status_code)
            }
        )

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

    if tornado.options.options.logfile is not None and tornado.options.options.timings_log_enabled:
        timings_log.addHandler(TimingsLoggingHandler())
        timings_log.propagate = False
    else:
        timings_log.disabled = True

    for log_channel_name in tornado.options.options.suppressed_loggers:
        logging.getLogger(log_channel_name).setLevel(logging.WARN)
