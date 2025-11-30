from __future__ import annotations

import logging
import os
import socket
import time
from functools import cache
from logging import Filter, Formatter, Handler
from logging.handlers import SysLogHandler
from pathlib import Path
from typing import IO, TYPE_CHECKING, Optional, Union

from tornado.log import LogFormatter

from frontik.options import options
from frontik.request_integrations import request_context
from frontik.util.json import json_encode

if TYPE_CHECKING:
    from logging import LogRecord

ROOT_LOGGER = logging.root
JSON_REQUESTS_LOGGER = logging.getLogger('requests')

CUSTOM_JSON_EXTRA = 'custom_json'


class Mdc:
    def __init__(self) -> None:
        self.role: Union[str, None] = None

    def init(self, role: Union[str, None] = None) -> None:
        self.role = role


MDC = Mdc()


class ContextFilter(Filter):
    def filter(self, record):
        handler_name = request_context.get_handler_name()
        record.name = '.'.join(filter(None, [record.name, handler_name]))
        return True


_CONTEXT_FILTER = ContextFilter()


class BufferedHandler(Handler):
    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self.records: list[LogRecord] = []

    def handle(self, record: logging.LogRecord) -> None:  # type: ignore
        self.records.append(record)

    def produce_all(self):
        raise NotImplementedError()  # pragma: no cover


class DebugLogHandler(Handler):
    def handle(self, record):
        handler = request_context.get_debug_log_handler()
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

        if options.log_write_appender_name:
            logger = logging.getLogger(record.name)
            json_message['appender'] = _get_logger_filename(logger)

        custom_json = getattr(record, CUSTOM_JSON_EXTRA, None)
        if custom_json:
            json_message.update(custom_json)
        else:
            json_message['lvl'] = record.levelname
            json_message['logger'] = record.name
            json_message['mdc'] = mdc
            json_message['msg'] = message

            if stack_trace:
                json_message['exception'] = stack_trace

        return json_encode(json_message)

    @staticmethod
    def get_mdc() -> dict:
        mdc: dict = {'thread': os.getpid()}

        if MDC.role is not None:
            mdc['role'] = MDC.role

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
            if stack_trace[-1:] != '\n':
                stack_trace += '\n'
            stack_trace += record.exc_text
        if record.stack_info:
            if stack_trace[-1:] != '\n':
                stack_trace += '\n'
            stack_trace += self.formatStack(record.stack_info)

        return stack_trace


JSON_FORMATTER = JSONFormatter()


class StderrFormatter(LogFormatter):
    def format(self, record):
        if not record.msg:
            record.msg = ', '.join(f'{k}={v}' for k, v in getattr(record, CUSTOM_JSON_EXTRA, {}).items())

        formatted_message = super().format(record)

        if options.log_write_appender_name:
            logger = logging.getLogger(record.name)
            appender_name = _get_logger_filename(logger)
            formatted_message = f'["appender":"{appender_name}"] {formatted_message}'

        return formatted_message


class TextFormatter(Formatter):
    def format(self, record: LogRecord) -> str:
        formatted_message = super().format(record)

        if options.log_write_appender_name:
            logger = logging.getLogger(record.name)
            appender_name = _get_logger_filename(logger)
            formatted_message = f'["appender":"{appender_name}"] {formatted_message}'

        return formatted_message


@cache
def get_stderr_formatter() -> StderrFormatter:
    return StderrFormatter(fmt=options.stderr_format, datefmt=options.stderr_dateformat)


@cache
def get_text_formatter() -> TextFormatter:
    return TextFormatter(options.log_text_format)


def bootstrap_logger(
    logger_info: Union[str, tuple[logging.Logger, str]],
    logger_level: int,
    use_json_formatter: bool = True,
    *,
    formatter: Optional[Formatter] = None,
) -> logging.Logger:
    if isinstance(logger_info, tuple):
        logger, logger_name = logger_info
    else:
        logger, logger_name = logging.getLogger(logger_info), logger_info

    log_extension = '.slog' if use_json_formatter else '.rlog'
    logger.appender = logger_name + log_extension  # type: ignore[attr-defined]
    handlers = []

    if options.log_dir:
        handlers.extend(_configure_file(logger, use_json_formatter, formatter))

    if options.stderr_log:
        handlers.extend(_configure_stderr(use_json_formatter=use_json_formatter, formatter=formatter))

    if options.syslog:
        handlers.extend(_configure_syslog(logger, use_json_formatter, formatter))

    for handler in handlers:
        handler.setLevel(logger_level)
        logger.addHandler(handler)

    logger.addHandler(DebugLogHandler())
    logger.propagate = False

    return logger


def _get_logger_filename(logger: logging.Logger) -> str:
    return getattr(logger, 'appender', ROOT_LOGGER.appender)  # type: ignore[return-value, attr-defined]


def _configure_file(
    logger: logging.Logger,
    use_json_formatter: bool = True,
    formatter: Optional[Formatter] = None,
) -> list[Handler]:
    assert options.log_dir is not None
    filename = _get_logger_filename(logger)

    file_handler = logging.handlers.WatchedFileHandler(Path(options.log_dir) / f'{filename}')

    if formatter is not None:
        file_handler.setFormatter(formatter)
    elif use_json_formatter:
        file_handler.setFormatter(JSON_FORMATTER)
    else:
        file_handler.setFormatter(get_text_formatter())
        file_handler.addFilter(_CONTEXT_FILTER)

    return [file_handler]


def _configure_stderr(
    *,
    use_json_formatter: bool = True,
    formatter: Formatter | None = None,
) -> list[logging.StreamHandler[IO[str]]]:
    stderr_handler = logging.StreamHandler()
    if formatter is not None:
        stderr_handler.setFormatter(formatter)
    elif use_json_formatter:
        stderr_handler.setFormatter(JSON_FORMATTER)
    else:
        stderr_handler.setFormatter(get_stderr_formatter())
        stderr_handler.addFilter(_CONTEXT_FILTER)

    return [stderr_handler]


def _configure_syslog(
    logger: logging.Logger,
    use_json_formatter: bool = True,
    formatter: Optional[Formatter] = None,
) -> list[Handler]:
    filename = _get_logger_filename(logger)

    try:
        syslog_handler = SysLogHandler(
            address=(options.syslog_host, options.syslog_port),
            facility=SysLogHandler.facility_names[options.syslog_facility],
            socktype=socket.SOCK_DGRAM,
        )
        syslog_handler.ident = f'{options.syslog_tag}/{filename}/: '
        if formatter is not None:
            syslog_handler.setFormatter(formatter)
        elif use_json_formatter:
            syslog_handler.setFormatter(JSON_FORMATTER)
        else:
            syslog_handler.setFormatter(get_text_formatter())
            syslog_handler.addFilter(_CONTEXT_FILTER)

        return [syslog_handler]

    except OSError:
        logging.getLogger('frontik.logging').exception('cannot initialize syslog')
        return []


def bootstrap_core_logging(log_level: str, use_json: bool, suppressed_loggers: list[str]) -> None:
    """This is a replacement for standard Tornado logging configuration."""
    level = getattr(logging, log_level.upper())
    ROOT_LOGGER.setLevel(logging.NOTSET)

    bootstrap_logger((ROOT_LOGGER, 'service'), level, use_json_formatter=use_json)
    bootstrap_logger('server', level, use_json_formatter=use_json)

    if use_json:
        bootstrap_logger((JSON_REQUESTS_LOGGER, 'requests'), level, use_json_formatter=True)

    for logger_name in suppressed_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    logging.captureWarnings(True)
