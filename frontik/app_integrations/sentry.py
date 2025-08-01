from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional, cast

import sentry_sdk
from fastapi import HTTPException
from http_client.request_response import FailFastError
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.atexit import AtexitIntegration
from sentry_sdk.integrations.excepthook import ExcepthookIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration, StarletteIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.modules import ModulesIntegration
from sentry_sdk.integrations.stdlib import StdlibIntegration
from starlette.requests import ClientDisconnect

from frontik.app_integrations import Integration, integrations_logger
from frontik.balancing_client import OutOfRequestTime
from frontik.options import options

if TYPE_CHECKING:
    from asyncio import Future

    from sentry_sdk._types import Event as SentryEvent
    from sentry_sdk._types import Hint

    from frontik.app import FrontikApplication

    class Event(SentryEvent):
        trace: dict[str, Any]


def before_send(event: SentryEvent, hint: Hint) -> SentryEvent | None:
    event_dict = cast('dict[str, Any]', event)
    event_dict['trace'] = event_dict.get('trace', {})
    old_trace_id = event_dict['trace'].get('trace_id')
    new_trace_id = event_dict.get('extra', {}).get('request_id', old_trace_id)

    if new_trace_id:
        event_dict['trace']['trace_id'] = new_trace_id
    return event


class SentryIntegration(Integration):
    def initialize_app(self, app: FrontikApplication) -> Optional[Future]:
        if not options.sentry_dsn:
            integrations_logger.info('sentry integration is disabled: sentry_dsn option is not configured')
            return None

        integrations = [
            AioHttpIntegration(),
            FastApiIntegration(),
            StarletteIntegration(),
            AtexitIntegration(),
            ModulesIntegration(),
            StdlibIntegration(),
        ]

        if options.sentry_exception_integration:
            integrations.append(ExcepthookIntegration())

        if options.sentry_logging_integration:
            integrations.append(LoggingIntegration())

        ignore_errors = [HTTPException, FailFastError, OutOfRequestTime, ClientDisconnect]
        if hasattr(app, 'get_sentry_ignored_exceptions'):
            ignore_errors += app.get_sentry_ignored_exceptions()

        sentry_sdk.init(
            dsn=options.sentry_dsn,
            max_breadcrumbs=options.sentry_max_breadcrumbs,
            default_integrations=False,
            auto_enabling_integrations=False,
            integrations=integrations,
            sample_rate=options.sentry_sample_rate,
            enable_tracing=options.sentry_enable_tracing,
            traces_sample_rate=options.sentry_traces_sample_rate,
            in_app_include=list(filter(None, options.sentry_in_app_include.split(','))),
            profiles_sample_rate=options.sentry_profiles_sample_rate,
            ignore_errors=ignore_errors,
            before_send=before_send,
        )

        logging.getLogger('sentry_sdk.errors').setLevel(logging.WARNING)

        return None

    def initialize_handler(self, handler):
        if not options.sentry_dsn:
            return

        if hasattr(handler, 'initialize_sentry_logger'):
            handler.initialize_sentry_logger()
