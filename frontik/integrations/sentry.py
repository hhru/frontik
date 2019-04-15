from asyncio import Future
from typing import Optional

from raven.contrib.tornado import AsyncSentryClient
from tornado.web import HTTPError

from frontik.options import options
from frontik.http_client import FailFastError
from frontik.integrations import Integration, integrations_logger


class SentryIntegration(Integration):
    def __init__(self):
        self.sentry_client = None

    def initialize_app(self, app) -> Optional[Future]:
        if not options.sentry_dsn:
            integrations_logger.info('sentry integration is disabled: sentry_dsn option is not configured')
            return

        self.sentry_client = FrontikAsyncSentryClient(
            dsn=options.sentry_dsn, http_client=app.http_client_factory.tornado_http_client,
            release=app.application_version(),
            # breadcrumbs have serious performance penalties
            enable_breadcrumbs=False, install_logging_hook=False, install_sys_hook=False
        )
        return None

    def initialize_handler(self, handler):
        if self.sentry_client is None:
            return

        def get_sentry_logger():
            if not hasattr(handler, 'sentry_logger'):
                handler.sentry_logger = SentryLogger(self.sentry_client, handler.request)
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


class FrontikAsyncSentryClient(AsyncSentryClient):
    def __init__(self, *args, http_client=None, **kwargs):
        self.http_client = http_client
        super().__init__(*args, **kwargs)

    def _send_remote(self, url, data, headers=None, callback=None):
        """
        Initialise a Tornado AsyncClient and send the request to the sentry
        server. If the callback is a callable, it will be called with the
        response.
        """
        return self.http_client.fetch(
            url, callback, method='POST', body=data, headers=headers if headers else {},
            validate_cert=self.validate_cert, connect_timeout=options.http_client_default_connect_timeout_sec,
            request_timeout=options.http_client_default_request_timeout_sec
        )


class SentryLogger:
    def __init__(self, sentry_client, request):
        """
        :type request: tornado.httpserver.HTTPRequest
        :type sentry_client: frontik.sentry.AsyncSentryClient
        """
        self.sentry_client = sentry_client
        self.request = request
        self.request_extra_data = {}
        self.user_info = {
            'ip_address': request.remote_ip,
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
            'ip_address': ip,
        }
        new_data = {k: v for k, v in new_data.items() if v is not None}
        self.user_info.update(new_data)

    def capture_exception(self, exc_info=None, extra_data=None, **kwargs):
        """
        Additional kwargs passed to raven.base.Client#captureException:
        """
        sentry_data = self._collect_sentry_data(extra_data)
        self.sentry_client.captureException(exc_info=exc_info, data=sentry_data, **kwargs)

    def capture_message(self, message, extra_data=None, **kwargs):
        """
        Additional kwargs passed to raven.base.Client#captureMessage:
        """
        sentry_data = self._collect_sentry_data(extra_data)
        self.sentry_client.captureMessage(message, data=sentry_data, **kwargs)

    def _collect_sentry_data(self, extra_data):
        data = {
            # url and method are required
            # see http://sentry.readthedocs.org/en/latest/developer/interfaces/#sentry.interfaces.http.Http
            'request': {
                'url': self.url,
                'method': self.request.method,
                'data': self.request.body,
                'query_string': self.request.query,
                'cookies': self.request.headers.get('Cookie', None),
                'headers': dict(self.request.headers),
            },

            # either user id or ip_address is required
            # see http://sentry.readthedocs.org/en/latest/developer/interfaces/#sentry.interfaces.user.User
            'user': self.user_info,

            'extra': {}
        }
        if extra_data:
            data['extra']['extra_data'] = extra_data
        if self.request_extra_data:
            data['extra']['request_extra_data'] = self.request_extra_data
        return data
