from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import sentry_sdk
from sentry_sdk.api import continue_trace
from sentry_sdk.consts import OP
from sentry_sdk.integrations import Integration
from sentry_sdk.integrations._wsgi_common import RequestExtractor, _filter_headers, _is_json_content_type
from sentry_sdk.tracing import TransactionSource
from sentry_sdk.utils import capture_internal_exceptions
from tornado.httputil import HTTPServerRequest

from frontik.options import options
from frontik.request_integrations.integrations_dto import IntegrationDto

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from frontik.app import FrontikApplication


class FrontikIntegration(Integration):
    identifier = 'frontik'
    origin = f'auto.http.{identifier}'

    @staticmethod
    def setup_once():
        pass


class TornadoRequestExtractor(RequestExtractor):
    def content_length(self):
        if self.request.body is None:
            return 0
        return len(self.request.body)

    def cookies(self):
        return {k: v.value for k, v in self.request.cookies.items()}

    def raw_data(self):
        return self.request.body

    def form(self):
        return {k: [v.decode('latin1', 'replace') for v in vs] for k, vs in self.request.body_arguments.items()}

    def is_json(self):
        return _is_json_content_type(self.request.headers.get('content-type'))

    def files(self):
        return {k: v[0] for k, v in self.request.files.items() if v}

    def size_of_file(self, file):
        return len(file.body or ())


def _make_event_processor(request: HTTPServerRequest) -> Callable:
    def tornado_processor(event, _hint):
        with capture_internal_exceptions():
            event['transaction'] = 'temporarily_undefined'
            event['transaction_info'] = {'source': TransactionSource.COMPONENT}

            extractor = TornadoRequestExtractor(request)
            extractor.extract_into_event(event)

            request_info = event['request']
            request_info['url'] = '%s://%s%s' % (
                request.protocol,
                request.host,
                request.path,
            )

            request_info['query_string'] = request.query
            request_info['method'] = request.method
            request_info['env'] = {'REMOTE_ADDR': real_ip(request)}
            request_info['headers'] = _filter_headers(dict(request.headers))

        return event

    return tornado_processor


def real_ip(request: HTTPServerRequest) -> str:
    return request.headers.get('X-Real-Ip', None) or request.remote_ip or '127.127.127.127'


@contextmanager
def request_context(_frontik_app: FrontikApplication, tornado_request: HTTPServerRequest) -> Iterator:
    if not options.sentry_dsn:
        yield IntegrationDto()
        return

    integration = sentry_sdk.get_client().get_integration(FrontikIntegration)
    if integration is None:
        yield IntegrationDto()
        return

    with sentry_sdk.isolation_scope() as scope:
        headers = tornado_request.headers

        scope.clear_breadcrumbs()
        processor = _make_event_processor(tornado_request)
        scope.add_event_processor(processor)

        transaction = continue_trace(
            headers,  # type: ignore
            op=OP.HTTP_SERVER,
            name='generic Tornado request',
            source=TransactionSource.ROUTE,
            origin=FrontikIntegration.origin,
        )

        with sentry_sdk.start_transaction(transaction, custom_sampling_context={'tornado_request': tornado_request}):
            yield IntegrationDto()
