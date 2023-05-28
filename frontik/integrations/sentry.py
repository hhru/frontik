from asyncio import Future
from typing import Optional

import sentry_sdk
from http_client import FailFastError
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
            traces_sample_rate=0,
            max_breadcrumbs=0,
            default_integrations=False,
            auto_enabling_integrations=False,
            integrations=[
                TornadoIntegration(),
            ],
        )

        def get_sentry_logger(request):
            return SentryLogger(request)

        app.get_sentry_logger = get_sentry_logger

        return None

    def initialize_handler(self, handler):
        if not options.sentry_dsn:
            return

        def get_sentry_logger():
            if not hasattr(handler, 'sentry_logger'):
                handler.sentry_logger = handler.application.get_sentry_logger(handler.request)
                if hasattr(handler, 'initialize_sentry_logger'):
                    handler.initialize_sentry_logger(handler.sentry_logger)

            return handler.sentry_logger

        # Defer logger creation after exception actually occurs
        def log_exception_to_sentry(typ, value, tb):
            if isinstance(value, (HTTPError, FailFastError)):
                return

            handler.get_sentry_logger().capture_exception(exc_info=(typ, value, tb))

        handler.get_sentry_logger = get_sentry_logger
        handler.register_exception_hook(log_exception_to_sentry)


class SentryLogger:
    def __init__(self, request):
        """
        :type request: tornado.httpserver.HTTPRequest
        """
        self.request = request
        self.request_extra_data = {}
        self.user_info = {
            'real_ip': request.remote_ip,
        }
        self.url = request.full_url()

    def set_request_extra_data(self, request_extra_data):
        """
        :type request_extra_data: dict
        :param request_extra_data: extra data to be sent with any exception or message
        """
        self.request_extra_data = request_extra_data

    def update_user_info(self, user_id=None, ip=None, username=None, email=None):
        new_data = {
            'id': user_id,
            'username': username,
            'email': email,
            'real_ip': ip,
        }
        new_data = {k: v for k, v in new_data.items() if v is not None}
        self.user_info.update(new_data)

    def capture_exception(self, exc_info=None, extra_data=None, **kwargs):
        sentry_data = self._collect_sentry_data(extra_data)
        with sentry_sdk.configure_scope() as scope:
            scope.set_user(self.user_info)
            for k, v in sentry_data['extras'].items():
                scope.set_extra(k, v)

    def capture_message(self, message, extra_data=None, **kwargs):
        sentry_data = self._collect_sentry_data(extra_data)
        sentry_sdk.capture_message(message, **(kwargs | sentry_data))

    def _collect_sentry_data(self, extra_data):
        data = {
            # either user id or ip_address is required
            # see http://sentry.readthedocs.org/en/latest/developer/interfaces/#sentry.interfaces.user.User
            'user': self.user_info,
            'extras': {},
        }
        if extra_data:
            data['extras']['extra_data'] = extra_data
        if self.request_extra_data:
            data['extras']['request_extra_data'] = self.request_extra_data
        return data
