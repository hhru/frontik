from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tornado.httputil import HTTPServerRequest

    from frontik.debug import DebugBufferedHandler
    from frontik.handler import PageHandler


@dataclass(slots=True)
class _Context:
    request: HTTPServerRequest | None
    request_id: str | None
    handler: PageHandler | None = None
    handler_name: str | None = None
    log_handler: DebugBufferedHandler | None = None


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


def get_request_id() -> str | None:
    return _context.get().request_id


def get_handler_name() -> str | None:
    return _context.get().handler_name


def set_handler_name(handler_name: str) -> None:
    _context.get().handler_name = handler_name


def set_handler(handler: PageHandler) -> None:
    context = _context.get()
    context.handler_name = repr(handler)
    context.handler = handler


def current_handler() -> PageHandler:
    return _context.get().handler  # type: ignore[return-value]


def get_log_handler() -> DebugBufferedHandler | None:
    return _context.get().log_handler


def set_log_handler(log_handler: DebugBufferedHandler) -> None:
    _context.get().log_handler = log_handler
