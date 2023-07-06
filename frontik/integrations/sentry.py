from asyncio import Future
from typing import Optional

import sentry_sdk
from http_client.request_response import FailFastError
from sentry_sdk.integrations.tornado import TornadoIntegration
from tornado.web import HTTPError

from frontik.integrations import Integration, integrations_logger
from frontik.options import options


class SentryIntegration(Integration):
    def initialize_app(self, app) -> Optional[Future]:
        if not options.sentry_dsn:
            integrations_logger.info('sentry integration is disabled: sentry_dsn option is not configured')
            return

        sentry_sdk.init(
            dsn=options.sentry_dsn,
            release=app.application_version(),
            max_breadcrumbs=options.sentry_max_breadcrumbs,
            default_integrations=False,
            auto_enabling_integrations=False,
            integrations=[
                TornadoIntegration(),
            ],
            ignore_errors=[HTTPError, FailFastError]
        )

        return None

    def initialize_handler(self, handler):
        if not options.sentry_dsn:
            return

        if hasattr(handler, 'initialize_sentry_logger'):
            handler.initialize_sentry_logger()
