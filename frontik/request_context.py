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
    __slots__ = ('request', 'request_id', 'handler_name', 'log_handler')

    def __init__(self, request: Optional[HTTPServerRequest], request_id: Optional[str]) -> None:
        self.request = request
        self.request_id = request_id
        self.handler_name: Optional[str] = None
        self.log_handler: Optional[DebugBufferedHandler] = None


_context = contextvars.ContextVar('context', default=_Context(None, None))


@contextmanager
def request_context(request: HTTPServerRequest, request_id: str) -> Iterator:
    token = _context.set(_Context(request, request_id))
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


def set_handler_name(handler_name: str) -> None:
    _context.get().handler_name = handler_name


def set_handler(handler: PageHandler) -> None:
    context = _context.get()
    context.handler_name = repr(handler)


def get_log_handler() -> Optional[DebugBufferedHandler]:
    return _context.get().log_handler


def set_log_handler(log_handler: DebugBufferedHandler) -> None:
    _context.get().log_handler = log_handler
