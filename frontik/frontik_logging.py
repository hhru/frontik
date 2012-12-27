# -*- coding: utf-8 -*-
from collections import namedtuple
import copy

import logging
from logging.handlers import SysLogHandler
import traceback
import weakref
import time
import tornado.options
from lxml.builder import E
try:
    from graypy.handler import GELFHandler, LAN_CHUNK
except ImportError:
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

class BulkGELFHandler(GELFHandler):

    def handle_bulk(self, records_list, stages= None, status_code=None, exception=None, **kw):

        if records_list != []:
            first_record = records_list[0]
        else:
            return
        record_for_gelf = copy.deepcopy(first_record)
        record_for_gelf.message ="{0} {1} {2} \n".format(record_for_gelf.asctime,record_for_gelf.levelname, record_for_gelf.message)

        record_for_gelf.exc_info = exception
        for record in records_list[1:]:
            if record.levelno > record_for_gelf.levelno:
                record_for_gelf.levelno = record.levelno
                record_for_gelf.lineno=record.lineno
                record_for_gelf.filename=record.filename
            if record.exc_info is not None:
                record_for_gelf.exc_info=traceback.format_exc(record.exc_info)
            record_for_gelf.message +=" {0} {1} {2} \n".format(record.asctime, record.levelname,record.message)
        if stages is not None:
            for stage_name, stage_start, stage_delta in stages:
                setattr(record_for_gelf,stage_name,str(stage_delta - stage_start))

        record_for_gelf.code = status_code
        GELFHandler.handle(self, record_for_gelf)


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
                    self.records_list.append(self.process_record(record))

            def process_record(self,record):
                return record

            def add_bulk_handler(self, bulk_handler):
                self.bulk_handlers.append(bulk_handler)

            def get_records_list(self):
                return self.records_list


            def flush(self, **kw):
                for handler in self.bulk_handlers:
                    handler.handle_bulk(self.records_list, **kw)

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
                '_stages': E.stages(*[E.stage(str(st.delta*1000), {'name':str(st.name)}) for st in self.stages])
            })

    def process(self, msg, kwargs):
        if "extra" in kwargs:
            kwargs["extra"].update(self.extra)
        else :
            kwargs["extra"] = self.extra
        return msg, kwargs

    def request_finish_hook(self, exception = None):
        self.logger.flush(status_code=self.handler_ref()._status_code, stages=self.stages, exception=exception)

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

    if tornado.options.options.logfile is not None:
        logging.getLogger().addHandler(MonikInfoLoggingHandler())

    for log_channel_name in tornado.options.options.suppressed_loggers:
        logging.getLogger(log_channel_name).setLevel(logging.WARN)
