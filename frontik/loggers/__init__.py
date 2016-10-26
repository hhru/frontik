# coding=utf-8

import logging
from logging.handlers import SysLogHandler
import socket

from tornado.log import LogFormatter
from tornado.options import options

from frontik.loggers import sentry

"""Contains a list of all available third-party loggers, that can be used in the request handler.

Each third-party logger must be implemented as a separate module in `frontik.loggers` package.
The module must contain a callable named `bootstrap_logger`, which takes an instance of Tornado application
as the only parameter. `bootstrap_logger` is called only once when the application is loading and should contain
all initialization logic for the logger.

If the initialization was successful, `bootstrap_logger` should return a callable, which takes an instance of a
request handler. It will be called when a request handler is starting and should provide an initialization code
for this request handler (for example, add some specific methods for the handler or register hooks).
"""
LOGGERS = (sentry, )


class BufferedHandler(logging.Logger):
    def __init__(self, name, level=logging.NOTSET):
        super(BufferedHandler, self).__init__(name, level)
        self.records = []

    def handle(self, record):
        self.records.append(record)

    def produce_all(self):
        raise NotImplementedError()


def bootstrap_app_loggers(app):
    return [logger.bootstrap_logger(app) for logger in LOGGERS if logger is not None]


def bootstrap_core_logging():
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
        handler = logging.StreamHandler()
        handler.setFormatter(
            LogFormatter(fmt=options.stderr_format, datefmt=options.stderr_dateformat)
        )

        handler.setLevel(level)
        root_logger.addHandler(handler)

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
            syslog_handler.setLevel(level)
            root_logger.addHandler(syslog_handler)
        except socket.error:
            logging.getLogger('frontik.logging').exception('cannot initialize syslog')

    for logger_name in options.suppressed_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARN)

    if not root_logger.handlers:
        root_logger.addHandler(logging.NullHandler())
