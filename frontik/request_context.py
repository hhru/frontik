from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING, Optional

from fastapi.routing import APIRoute

if TYPE_CHECKING:
    from frontik.debug import DebugBufferedHandler


class _Context:
    __slots__ = ('handler_name', 'log_handler', 'request_id')

    def __init__(self, request_id: Optional[str]) -> None:
        self.request_id = request_id
        self.handler_name: Optional[str] = None
        self.log_handler: Optional[DebugBufferedHandler] = None


_context = contextvars.ContextVar('context', default=_Context(None))


def get_request_id() -> Optional[str]:
    return _context.get().request_id


def get_handler_name() -> Optional[str]:
    return _context.get().handler_name


def set_handler_name(route: APIRoute) -> None:
    _context.get().handler_name = f'{route.endpoint.__module__}.{route.endpoint.__name__}'


def get_log_handler() -> Optional[DebugBufferedHandler]:
    return _context.get().log_handler


def set_log_handler(log_handler: DebugBufferedHandler) -> None:
    _context.get().log_handler = log_handler
