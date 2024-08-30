from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

from http_client import client_request_context, response_status_code_context
from http_client.options import options as http_client_options
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation import aiohttp_client
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import IdGenerator, TracerProvider
from opentelemetry.sdk.trace import Span as SpanImpl
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.util.http import ExcludeList

from frontik import request_context
from frontik.integrations import Integration, integrations_logger, tornado
from frontik.options import options

if TYPE_CHECKING:
    from asyncio import Future

    import aiohttp
    from http_client.request_response import RequestBuilder
    from opentelemetry.trace import Span
    from opentelemetry.util import types

    from frontik.app import FrontikApplication

log = logging.getLogger('telemetry')
# change log-level, because mainly detach context produce exception on Tornado 5. Will be deleted, when up Tornado to 6
logging.getLogger('opentelemetry.context').setLevel(logging.CRITICAL)
set_global_textmap(TraceContextTextMapPropagator())

tornado._excluded_urls = ExcludeList([*list(tornado._excluded_urls._excluded_urls), '/status'])
excluded_span_attributes = ['tornado.handler']


class TelemetryIntegration(Integration):
    def __init__(self):
        self.aiohttp_instrumentor = aiohttp_client.AioHttpClientInstrumentor()
        self.tornado_instrumentor = tornado.TornadoInstrumentor()
        TelemetryIntegration.patch_span_impl()

    @staticmethod
    def patch_span_impl() -> None:
        set_attribute = SpanImpl.set_attribute

        def patched_set_attribute(self: SpanImpl, key: str, value: types.AttributeValue) -> None:
            if key not in excluded_span_attributes:
                return set_attribute(self, key, value)

        SpanImpl.set_attribute = patched_set_attribute  # type: ignore

    def initialize_app(self, app: FrontikApplication) -> Optional[Future]:
        if not options.opentelemetry_enabled:
            return None

        integrations_logger.info('start telemetry')

        resource = Resource(
            attributes={
                ResourceAttributes.SERVICE_NAME: app.app_name,
                ResourceAttributes.SERVICE_VERSION: app.application_version(),  # type: ignore
                ResourceAttributes.HOST_NAME: options.node_name,
                ResourceAttributes.CLOUD_REGION: http_client_options.datacenter,
            },
        )
        otlp_exporter = OTLPSpanExporter(endpoint=options.opentelemetry_collector_url, insecure=True)

        provider = TracerProvider(
            resource=resource,
            id_generator=FrontikIdGenerator(),
            sampler=ParentBased(TraceIdRatioBased(options.opentelemetry_sampler_ratio)),
        )

        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(provider)

        self.aiohttp_instrumentor.instrument(request_hook=_client_request_hook, response_hook=_client_response_hook)
        self.tornado_instrumentor.instrument(server_request_hook=_server_request_hook)
        return None

    def deinitialize_app(self, app: FrontikApplication) -> Optional[Future]:
        if not options.opentelemetry_enabled:
            return None

        integrations_logger.info('stop telemetry')
        self.aiohttp_instrumentor.uninstrument()
        self.tornado_instrumentor.uninstrument()
        return None

    def initialize_handler(self, handler):
        pass


def _server_request_hook(span, handler):
    if (handler_name := request_context.get_handler_name()) is not None:
        method_path, method_name = handler_name.rsplit('.', 1)
        span.update_name(f'{method_path}.{method_name}')
        span.set_attribute(SpanAttributes.CODE_FUNCTION, method_name)
        span.set_attribute(SpanAttributes.CODE_NAMESPACE, method_path)

    span.set_attribute(SpanAttributes.HTTP_TARGET, handler.request.uri)


def _client_request_hook(span: Span, params: aiohttp.TraceRequestStartParams) -> None:
    if not span or not span.is_recording():
        return

    request: RequestBuilder = client_request_context.get(None)
    if request is None:
        return

    upstream_datacenter = getattr(request, 'upstream_datacenter', None)
    upstream_hostname = getattr(request, 'upstream_hostname', None)
    upstream_name = getattr(request, 'upstream_name', None)
    if upstream_name is None:
        upstream_name = get_netloc(request.url)
    if upstream_hostname is None:
        upstream_hostname = 'unknown'

    span.update_name(' '.join(el for el in [request.method, upstream_name] if el))
    span.set_attribute(SpanAttributes.PEER_SERVICE, upstream_name)
    span.set_attribute('http.request.timeout', request.request_timeout * 1000)
    span.set_attribute('destination.address', upstream_hostname)
    if upstream_datacenter is not None:
        span.set_attribute('http.request.cloud.region', upstream_datacenter)

    return


def _client_response_hook(
    span: Span,
    params: aiohttp.TraceRequestEndParams | aiohttp.TraceRequestExceptionParams,
) -> None:
    if not span or not span.is_recording():
        return
    response_status_code: int = response_status_code_context.get(None)
    if response_status_code is None:
        return
    span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response_status_code)


def get_netloc(url: str) -> str:
    parts = urlparse(url)
    if parts.scheme not in ('http', 'https', ''):
        parts = urlparse('//' + url)

    return parts.netloc


class FrontikIdGenerator(IdGenerator):
    def generate_span_id(self) -> int:
        return random.getrandbits(64)

    def generate_trace_id(self) -> int:
        request_id = request_context.get_request_id()
        try:
            if request_id is None:
                msg = 'bad request_id'
                raise Exception(msg)

            if len(request_id) < 32:
                log.debug('request_id = %s is less than 32 characters. Generating random trace_id', request_id)
                return random.getrandbits(128)

            return int(request_id[:32], 16)
        except Exception:
            log.debug('request_id = %s is not valid hex-format. Generating random trace_id', request_id)
        return random.getrandbits(128)
