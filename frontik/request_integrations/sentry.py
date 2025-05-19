from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import sentry_sdk
from tornado.httputil import HTTPServerRequest

from frontik.options import options
from frontik.request_integrations.integrations_dto import IntegrationDto

if TYPE_CHECKING:
    from collections.abc import Iterator

    from frontik.app import FrontikApplication


@contextmanager
def sentry_context(_frontik_app: FrontikApplication, tornado_request: HTTPServerRequest) -> Iterator[IntegrationDto]:
    if options.sentry_dsn:
        sentry_sdk.set_extra('request_id', tornado_request.request_id)  # type: ignore[attr-defined]

    yield IntegrationDto()
