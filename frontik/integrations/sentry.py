from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration, StarletteIntegration

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
            integrations=[FastApiIntegration(), StarletteIntegration()],
        )

        return None

    def initialize_handler(self, handler):
        if not options.sentry_dsn:
            return

        if hasattr(handler, 'initialize_sentry_logger'):
            handler.initialize_sentry_logger()
