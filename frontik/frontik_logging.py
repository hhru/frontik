# -*- coding: utf-8 -*-
from collections import namedtuple
import logging
from logging.handlers import SysLogHandler
import weakref
import time
import tornado.options
from lxml.builder import E

log = logging.getLogger('frontik.handler')

class ContextFilter(logging.Filter):
    def filter(self, record):
        record.name = '.'.join(filter(None, [record.name, getattr(record, 'request_id', None)]))
        return True

log.addFilter(ContextFilter())


class MonikInfoLoggingFilter(logging.Filter):
    def filter(self, record):
        return getattr(record, '_monik', False)

class MonikInfoLoggingHandler(logging.FileHandler):
    def __init__(self):
        logging.FileHandler.__init__(self, self.__get_logfile_name())
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

    def __init__(self, msg_max_length = STD_MSG_LENGTH_LIMIT, *args, **kwargs):
        if msg_max_length >= self.MIN_MSG_LENGTH_LIMIT:
            self.max_length = msg_max_length
        else:
            self.max_length = self.STD_MSG_LENGTH_LIMIT
        SysLogHandler.__init__(self, *args, **kwargs)

    def format(self, record):
        """
        prio_length is length of '<prio>' header which is attached to message before sending to syslog
        so we need to subtract it from max_length to guarantee that length of resulting message won't be greater than max_length
        """
        prio_length = len('%d' % self.encodePriority(self.facility, self.mapPriority(record.levelname))) + 2 # 2 is length of angle brackets
        return SysLogHandler.format(self, record)[:(self.max_length - prio_length)]


class PageLogger(logging.LoggerAdapter):

    Stage = namedtuple('Stage', ['name', 'start', 'delta'])

    def __init__(self, handler, logger_name, page):

        class Logger4Adapter(logging.Logger):
            def handle(self, record):
                logging.Logger.handle(self, record)
                log.handle(record)

        self.handler_ref = weakref.ref(handler)
        self.handler_started = self.handler_ref().handler_started
        logging.LoggerAdapter.__init__(self, Logger4Adapter('frontik.handler'),
            dict(request_id=logger_name, page=page, handler=self.handler_ref().__module__))

        self._time = self.handler_started
        self.stages = []
        self.page = page
        # backcompatibility with logger
        self.warn = self.warning
        self.addHandler = self.logger.addHandler

    def stage_tag(self, stage_name):
        zero_time = self.handler_started
        self._stage_tag(PageLogger.Stage(stage_name, self._time - zero_time, time.time() - self._time))
        self._time = time.time()
        self.debug('Stage: {stage}'.format(stage=stage_name))

    def _stage_tag(self, stage):
        self.stages.append(stage)

    def process_stages(self, status_code):
        self._stage_tag(PageLogger.Stage('total', 0, time.time() - self.handler_started))

        format_f = lambda x: ' '.join([x.format(name=s.name, delta=1000*s.delta) for s in self.stages])
        stages_format = format_f('{name}:{delta:.2f}ms')
        stages_monik_format = format_f('{name}={delta:.2f}')

        self.debug('Stages for {0} : {1}'.format(self.page, stages_format))
        self.info('Monik-stages {0!r} : {1} code={2}'.format(self.handler_ref(), stages_monik_format, status_code),
            extra={
                '_monik': True,
                '_stages': E.stages(*[E.stage(str(v), {'name':str(k)}) for k, v in self.stages])
            })

    def process(self, msg, kwargs):
        if "extra" in kwargs:
            kwargs["extra"].update(self.extra)
        else :
            kwargs["extra"] = self.extra
        return msg, kwargs

def bootstrap_all_logging():
    server_log = logging.getLogger("frontik.server")

    if tornado.options.options.syslog:
        syslog_handler = MaxLenSysLogHandler(
            facility=MaxLenSysLogHandler.facility_names[
                     tornado.options.options.syslog_facility],
            address=tornado.options.options.syslog_address,
            msg_max_length=tornado.options.options.syslog_msg_max_length)
        syslog_handler.setFormatter(logging.Formatter(tornado.options.options.logformat))
        logging.getLogger().addHandler(syslog_handler)

    if tornado.options.options.graylog:
        try:
            from graypy import GELFHandler, WAN_CHUNK
            graylog_handler = GELFHandler(tornado.options.options.graylog_host,
                tornado.options.options.graylog_port, WAN_CHUNK, False)

            logging.getLogger().addHandler(graylog_handler)
        except ImportError:
            server_log.error('Graylog option is on, but can not import graypy and start graylog logging!')

    if tornado.options.options.logfile is not None:
        logging.getLogger().addHandler(MonikInfoLoggingHandler())

    for log_channel_name in tornado.options.options.suppressed_loggers:
        logging.getLogger(log_channel_name).setLevel(logging.WARN)
