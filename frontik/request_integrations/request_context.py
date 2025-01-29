from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional

from fastapi.routing import APIRoute
from tornado.httputil import HTTPServerRequest

from frontik.options import options
from frontik.request_integrations.integrations_dto import IntegrationDto
from frontik.util import check_request_id, generate_uniq_timestamp_request_id

if TYPE_CHECKING:
    from collections.abc import Iterator

    from frontik.app import FrontikApplication
    from frontik.debug import DebugBufferedHandler


class RequestContext:
    __slots__ = ('debug_log_handler', 'handler_name', 'request_id')

    def __init__(self, request_id: Optional[str]) -> None:
        self.request_id = request_id
        self.handler_name: Optional[str] = None
        self.debug_log_handler: Optional[DebugBufferedHandler] = None


_request_context = contextvars.ContextVar('request_context', default=RequestContext(None))


def get_request_context() -> RequestContext:
    return _request_context.get()


def get_request_id() -> Optional[str]:
    return _request_context.get().request_id


def get_handler_name() -> Optional[str]:
    return _request_context.get().handler_name


def set_handler_name(route: APIRoute) -> None:
    _request_context.get().handler_name = f'{route.endpoint.__module__}.{route.endpoint.__name__}'


def get_debug_log_handler() -> Optional[DebugBufferedHandler]:
    return _request_context.get().debug_log_handler


def set_debug_log_handler(debug_log_handler: DebugBufferedHandler) -> None:
    _request_context.get().debug_log_handler = debug_log_handler


@contextmanager
def request_context(frontik_app: FrontikApplication, tornado_request: HTTPServerRequest) -> Iterator:
    request_id = tornado_request.headers.get('X-Request-Id') or generate_uniq_timestamp_request_id()
    if options.validate_request_id:
        check_request_id(request_id)
    tornado_request.request_id = request_id  # type: ignore

    cls = getattr(frontik_app, 'default_request_context_cls', RequestContext)

    token = _request_context.set(cls(request_id))
    try:
        yield IntegrationDto(request_id)
    finally:
        _request_context.reset(token)
