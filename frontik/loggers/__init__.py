import logging
import socket
from logging.handlers import SysLogHandler

from tornado.log import LogFormatter
from tornado.options import options

from frontik.loggers import sentry, statsd
from frontik.request_context import RequestContext

"""Contains a list of all available third-party loggers, that can be used in the request handler.

Each third-party logger must be implemented as a separate module in `frontik.loggers` package.
The module must contain a callable named `bootstrap_logger`, which takes an instance of Tornado application
as the only parameter. `bootstrap_logger` is called only once when the application is loading and should contain
all initialization logic for the logger.

If the initialization was successful, `bootstrap_logger` should return a callable, which takes an instance of a
request handler. It will be called when a request handler is starting and should provide an initialization code
for this request handler (for example, add some specific methods for the handler or register hooks).
"""
LOGGERS = (sentry, statsd)

ROOT_LOGGER = logging.root


class ContextFilter(logging.Filter):
    def filter(self, record):
        handler_name = RequestContext.get('handler_name')
        request_id = RequestContext.get('request_id')
        record.name = '.'.join(filter(None, [record.name, handler_name, request_id]))
        return True


class BufferedHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.records = []

    def handle(self, record):
        self.records.append(record)

    def produce_all(self):
        raise NotImplementedError()  # pragma: no cover


class GlobalLogHandler(logging.Handler):
    def handle(self, record):
        if RequestContext.get('log_handler'):
            RequestContext.get('log_handler').handle(record)


def bootstrap_app_loggers(app):
    return [logger.bootstrap_logger(app) for logger in LOGGERS if logger is not None]


def bootstrap_core_logging():
    """This is a replacement for standard Tornado logging configuration."""

    handlers = []
    level = getattr(logging, options.loglevel.upper())
    context_filter = ContextFilter()
    ROOT_LOGGER.setLevel(logging.NOTSET)

    if options.logfile:
        file_handler = logging.handlers.WatchedFileHandler(options.logfile)
        file_handler.setFormatter(logging.Formatter(options.logformat))
        handlers.append(file_handler)

    if options.stderr_log:
        stderr_handler = logging.StreamHandler()
        stderr_handler.setFormatter(
            LogFormatter(fmt=options.stderr_format, datefmt=options.stderr_dateformat)
        )

        handlers.append(stderr_handler)

    if options.syslog:
        if options.syslog_port is not None:
            syslog_address = (options.syslog_address, options.syslog_port)
        else:
            syslog_address = options.syslog_address

        try:
            syslog_formatter = logging.Formatter('{}: {}'.format(options.app, options.logformat))
            syslog_handler = SysLogHandler(
                facility=SysLogHandler.facility_names[options.syslog_facility],
                address=syslog_address
            )
            syslog_handler.setFormatter(syslog_formatter)
            handlers.append(syslog_handler)
        except socket.error:
            logging.getLogger('frontik.logging').exception('cannot initialize syslog')

    for logger_name in options.suppressed_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARN)

    for handler in handlers:
        handler.setLevel(level)
        handler.addFilter(context_filter)
        ROOT_LOGGER.addHandler(handler)

    ROOT_LOGGER.addHandler(GlobalLogHandler())

    if not ROOT_LOGGER.handlers:
        ROOT_LOGGER.addHandler(logging.NullHandler())

    logging.captureWarnings(True)
