from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from collections.abc import Iterator

    from frontik.debug import DebugBufferedHandler


class _Context:
    __slots__ = ('handler_name', 'log_handler', 'request_id')

    def __init__(self, request_id: Optional[str]) -> None:
        self.request_id = request_id
        self.handler_name: Optional[str] = None
        self.log_handler: Optional[DebugBufferedHandler] = None


_context = contextvars.ContextVar('context', default=_Context(None))


@contextmanager
def request_context(request_id: str) -> Iterator:
    token = _context.set(_Context(request_id))
    try:
        yield
    finally:
        _context.reset(token)


def get_request_id() -> Optional[str]:
    return _context.get().request_id


def get_handler_name() -> Optional[str]:
    return _context.get().handler_name


def set_handler_name(handler_name: str) -> None:
    _context.get().handler_name = handler_name


def get_log_handler() -> Optional[DebugBufferedHandler]:
    return _context.get().log_handler


def set_log_handler(log_handler: DebugBufferedHandler) -> None:
    _context.get().log_handler = log_handler
