from __future__ import annotations
import contextvars
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frontik.debug import DebugBufferedHandler
    from tornado.httputil import HTTPServerRequest


class _Context:
    __slots__ = ('request', 'request_id', 'handler_name', 'log_handler')

    def __init__(self, request: HTTPServerRequest|None, request_id: str|None) -> None:
        self.request = request
        self.request_id = request_id
        self.handler_name: str|None = None
        self.log_handler: DebugBufferedHandler|None = None


_context = contextvars.ContextVar('context', default=_Context(None, None))


def initialize(request: HTTPServerRequest, request_id: str) -> contextvars.Token:
    return _context.set(_Context(request, request_id))


def reset(token: contextvars.Token) -> None:
    _context.reset(token)


def get_request():
    return _context.get().request


def get_request_id() -> str|None:
    return _context.get().request_id


def get_handler_name() -> str | None:
    return _context.get().handler_name


def set_handler_name(handler_name: str) -> None:
    _context.get().handler_name = handler_name


def get_log_handler() -> DebugBufferedHandler|None:
    return _context.get().log_handler


def set_log_handler(log_handler: DebugBufferedHandler) -> None:
    _context.get().log_handler = log_handler
