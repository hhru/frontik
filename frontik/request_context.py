from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tornado.httputil import HTTPServerRequest

    from frontik.debug import DebugBufferedHandler
    from frontik.handler import PageHandler


class _Context:
    __slots__ = ('handler_name', 'log_handler', 'request', 'request_id')

    def __init__(self, request: Optional[HTTPServerRequest], request_id: Optional[str], handler_name) -> None:
        self.request = request
        self.request_id = request_id
        self.handler_name: str = handler_name
        self.log_handler: Optional[DebugBufferedHandler] = None


_context = contextvars.ContextVar('context', default=_Context(None, None, None))


@contextmanager
def request_context(request: HTTPServerRequest, request_id: str, handler) -> Iterator:
    token = _context.set(_Context(request, request_id, repr(handler)))
    try:
        yield
    finally:
        _context.reset(token)


def get_request():
    return _context.get().request


def get_request_id() -> Optional[str]:
    return _context.get().request_id


def get_handler_name() -> Optional[str]:
    return _context.get().handler_name


def get_log_handler() -> Optional[DebugBufferedHandler]:
    return _context.get().log_handler


def set_log_handler(log_handler: DebugBufferedHandler) -> None:
    _context.get().log_handler = log_handler
