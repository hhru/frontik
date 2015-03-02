# coding: utf-8
from tornado.httpclient import AsyncHTTPClient
from tornado.options import options

try:
    from raven.contrib.tornado import AsyncSentryClient as OriginalAsyncSentryClient
    has_raven = True
except ImportError:
    has_raven = False

if has_raven:
    class AsyncSentryClient(OriginalAsyncSentryClient):

        def __init__(self, *args, **kwargs):
            self.http_client = kwargs.pop('http_client', None)
            super(AsyncSentryClient, self).__init__(*args, **kwargs)

        def _send_remote(self, url, data, headers=None, callback=None):
            """
            Initialise a Tornado AsyncClient and send the request to the sentry
            server. If the callback is a callable, it will be called with the
            response.
            """
            http_client = self.http_client if self.http_client else AsyncHTTPClient()
            return http_client.fetch(
                url, callback, method="POST", body=data, headers=headers if headers else {},
                validate_cert=self.validate_cert, connect_timeout=options.http_client_default_connect_timeout,
                request_timeout=options.http_client_default_request_timeout
            )

    class SentryHandler(object):

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
            :param request_extra_data: data is sent with any exception or message
            """
            self.request_extra_data = request_extra_data

        def update_user_info(self, user_id=None, ip=None, username=None, email=None):
            new_data = {
                'id': user_id,
                'username': username,
                'email': email,
                'ip_address': ip,
            }
            new_data = {k: v for k, v in new_data.iteritems() if v is not None}
            self.user_info.update(new_data)

        def set_full_url(self, url):
            self.url = url

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
                # url & method are required
                # see http://sentry.readthedocs.org/en/latest/developer/interfaces/#sentry.interfaces.http.Http
                'request': {
                    'url': self.url,
                    'method': self.request.method,
                    'data': self.request.body,
                    'query_string': self.request.query,
                    'cookies': self.request.headers.get('Cookie', None),
                    'headers': dict(self.request.headers),
                },

                # either an id or ip_address is required
                # see http://sentry.readthedocs.org/en/latest/developer/interfaces/#sentry.interfaces.user.User
                'user': self.user_info,

                'extra': {}
            }
            if extra_data:
                data['extra']['extra_data'] = extra_data
            if self.request_extra_data:
                data['extra']['request_extra_data'] = self.request_extra_data
            return data

else:
    AsyncSentryClient = None
    SentryHandler = None
