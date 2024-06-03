from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import sentry_sdk
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.atexit import AtexitIntegration
from sentry_sdk.integrations.dedupe import DedupeIntegration
from sentry_sdk.integrations.excepthook import ExcepthookIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration, StarletteIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.modules import ModulesIntegration
from sentry_sdk.integrations.stdlib import StdlibIntegration

from frontik.integrations import Integration, integrations_logger
from frontik.options import options

if TYPE_CHECKING:
    from asyncio import Future

    from frontik.app import FrontikApplication


class SentryIntegration(Integration):
    def initialize_app(self, app: FrontikApplication) -> Optional[Future]:
        if not options.sentry_dsn:
            integrations_logger.info('sentry integration is disabled: sentry_dsn option is not configured')
            return None

        sentry_sdk.init(
            dsn=options.sentry_dsn,
            max_breadcrumbs=options.sentry_max_breadcrumbs,
            default_integrations=False,
            auto_enabling_integrations=False,
            integrations=[
                AioHttpIntegration(),
                FastApiIntegration(),
                StarletteIntegration(),
                AtexitIntegration(),
                DedupeIntegration(),
                ExcepthookIntegration(),
                ModulesIntegration(),
                StdlibIntegration(),
                LoggingIntegration(level=None, event_level=logging.WARNING),
            ],
            sample_rate=options.sentry_sample_rate,
            enable_tracing=options.sentry_enable_tracing,
            traces_sample_rate=options.sentry_traces_sample_rate,
            in_app_include=list(filter(None, options.sentry_in_app_include.split(','))),
        )

        return None

    def initialize_handler(self, handler):
        if not options.sentry_dsn:
            return

        if hasattr(handler, 'initialize_sentry_logger'):
            handler.initialize_sentry_logger()
