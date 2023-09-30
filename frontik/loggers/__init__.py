from __future__ import annotations
import json
import logging
import os
import socket
import time
from logging import Filter, Formatter, Handler
from logging.handlers import SysLogHandler
from typing import TYPE_CHECKING

from tornado.log import LogFormatter

from frontik import request_context
from frontik.options import options

if TYPE_CHECKING:
    from typing import List, Optional
    from logging import LogRecord

ROOT_LOGGER = logging.root
JSON_REQUESTS_LOGGER = logging.getLogger('requests')

CUSTOM_JSON_EXTRA = 'custom_json'


class Mdc:
    def __init__(self) -> None:
        self.pid: int = None  # type: ignore
        self.role: str = None  # type: ignore

    def init(self, role: str) -> None:
        self.pid = os.getpid()
        self.role = role


MDC = Mdc()


class ContextFilter(Filter):
    def filter(self, record):
        handler_name = request_context.get_handler_name()
        request_id = request_context.get_request_id()
        record.name = '.'.join(filter(None, [record.name, handler_name, request_id]))
        return True


_CONTEXT_FILTER = ContextFilter()


class BufferedHandler(Handler):
    def __init__(self, level:int=logging.NOTSET) -> None:
        super().__init__(level)
        self.records: list[LogRecord] = []

    def handle(self, record: logging.LogRecord) -> None:  # type: ignore
        self.records.append(record)

    def produce_all(self):
        raise NotImplementedError()  # pragma: no cover


class GlobalLogHandler(Handler):
    def handle(self, record):
        handler = request_context.get_log_handler()
        if handler is not None:
            handler.handle(record)


class JSONFormatter(Formatter):
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S.%%03d%z'

    def format(self, record):
        message = record.getMessage() if record.msg is not None else None
        timestamp = time.strftime(JSONFormatter.DATE_FORMAT, time.localtime(record.created)) % record.msecs
        stack_trace = self.format_stack_trace(record)
        mdc = JSONFormatter.get_mdc()

        json_message = {'ts': timestamp}

        custom_json = getattr(record, CUSTOM_JSON_EXTRA, None)
        if custom_json:
            json_message.update(custom_json)
        else:
            json_message.update(
                {
                    'lvl': record.levelname,
                    'logger': record.name,
                    'mdc': mdc,
                    'msg': message,
                }
            )

            if stack_trace:
                json_message['exception'] = stack_trace

        return json.dumps(json_message)

    @staticmethod
    def get_mdc() -> dict:
        mdc = {'thread': MDC.pid, 'role': MDC.role}

        handler_name = request_context.get_handler_name()
        if handler_name:
            mdc['controller'] = handler_name

        request_id = request_context.get_request_id()
        if request_id:
            mdc['rid'] = request_id

        return mdc

    def format_stack_trace(self, record: logging.LogRecord) -> str:
        # Copypaste from super.format
        stack_trace = ''
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if stack_trace[-1:] != "\n":
                stack_trace = stack_trace + "\n"
            stack_trace = stack_trace + record.exc_text
        if record.stack_info:
            if stack_trace[-1:] != "\n":
                stack_trace = stack_trace + "\n"
            stack_trace = stack_trace + self.formatStack(record.stack_info)

        return stack_trace


_JSON_FORMATTER = JSONFormatter()


class StderrFormatter(LogFormatter):
    def format(self, record):
        handler_name = request_context.get_handler_name()
        request_id = request_context.get_request_id()
        record.name = '.'.join(filter(None, [record.name, handler_name, request_id]))

        if not record.msg:
            record.msg = ', '.join(f'{k}={v}' for k, v in getattr(record, CUSTOM_JSON_EXTRA, {}).items())

        return super().format(record)


_STDERR_FORMATTER = None
_TEXT_FORMATTER = None


def get_stderr_formatter() -> StderrFormatter:
    global _STDERR_FORMATTER

    if _STDERR_FORMATTER is None:
        _STDERR_FORMATTER = StderrFormatter(fmt=options.stderr_format, datefmt=options.stderr_dateformat)

    return _STDERR_FORMATTER


def get_text_formatter() -> Formatter:
    global _TEXT_FORMATTER

    if _TEXT_FORMATTER is None:
        _TEXT_FORMATTER = Formatter(options.log_text_format)

    return _TEXT_FORMATTER


def bootstrap_logger(logger_info: str|tuple, logger_level: int, use_json_formatter:bool=True, *, formatter:Formatter|None=None) -> logging.Logger:
    if isinstance(logger_info, tuple):
        logger, logger_name = logger_info
    else:
        logger, logger_name = logging.getLogger(logger_info), logger_info

    handlers = []

    if options.log_dir:
        handlers.extend(_configure_file(logger_name, use_json_formatter, formatter))

    if options.stderr_log:
        handlers.extend(_configure_stderr(formatter))

    if options.syslog:
        handlers.extend(_configure_syslog(logger_name, use_json_formatter, formatter))

    for handler in handlers:
        handler.setLevel(logger_level)
        logger.addHandler(handler)

    logger.addHandler(GlobalLogHandler())
    logger.propagate = False

    return logger


def _configure_file(
    logger_name: str, use_json_formatter: bool = True, formatter: Formatter|None = None
) -> list[Handler]:
    log_extension = '.slog' if use_json_formatter else '.log'
    file_handler = logging.handlers.WatchedFileHandler(os.path.join(options.log_dir, f'{logger_name}{log_extension}'))  # type: ignore

    if formatter is not None:
        file_handler.setFormatter(formatter)
    elif use_json_formatter:
        file_handler.setFormatter(_JSON_FORMATTER)
    else:
        file_handler.setFormatter(get_text_formatter())
        file_handler.addFilter(_CONTEXT_FILTER)

    return [file_handler]


def _configure_stderr(formatter: Formatter|None = None) -> list[logging.StreamHandler]:
    stderr_handler = logging.StreamHandler()
    if formatter is not None:
        stderr_handler.setFormatter(formatter)
    else:
        stderr_handler.setFormatter(get_stderr_formatter())
        stderr_handler.addFilter(_CONTEXT_FILTER)

    return [stderr_handler]


def _configure_syslog(
    logger_name: str, use_json_formatter: bool = True, formatter: 'Optional[Formatter]' = None
) -> 'List[Handler]':
    try:
        syslog_handler = SysLogHandler(
            address=(options.syslog_host, options.syslog_port),
            facility=SysLogHandler.facility_names[options.syslog_facility],
            socktype=socket.SOCK_DGRAM,
        )
        log_extension = '.slog' if use_json_formatter else '.log'
        syslog_handler.ident = f'{options.syslog_tag}/{logger_name}{log_extension}/: '
        if formatter is not None:
            syslog_handler.setFormatter(formatter)
        elif use_json_formatter:
            syslog_handler.setFormatter(_JSON_FORMATTER)
        else:
            syslog_handler.setFormatter(get_text_formatter())
            syslog_handler.addFilter(_CONTEXT_FILTER)

        return [syslog_handler]

    except socket.error:
        logging.getLogger('frontik.logging').exception('cannot initialize syslog')
        return []


def bootstrap_core_logging(log_level: str, use_json: bool, suppressed_loggers: list[str]) -> None:
    """This is a replacement for standard Tornado logging configuration."""

    level = getattr(logging, log_level.upper())
    ROOT_LOGGER.setLevel(logging.NOTSET)

    bootstrap_logger((ROOT_LOGGER, 'service'), level, use_json_formatter=use_json)

    if use_json:
        bootstrap_logger((JSON_REQUESTS_LOGGER, 'requests'), level, use_json_formatter=True)

    for logger_name in suppressed_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARN)

    logging.captureWarnings(True)
