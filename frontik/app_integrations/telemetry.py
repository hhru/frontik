from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

from http_client import current_client_request, current_client_request_status
from http_client.options import options as http_client_options
from http_client.request_response import OUTER_TIMEOUT_MS_HEADER
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GrpcExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HttpExporter
from opentelemetry.instrumentation import aiohttp_client
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor  # type: ignore
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import IdGenerator, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from frontik.app_integrations import Integration, integrations_logger
from frontik.options import options
from frontik.request_integrations import request_context

if TYPE_CHECKING:
    from asyncio import Future

    import aiohttp
    from http_client.request_response import RequestBuilder
    from opentelemetry.trace import Span

    from frontik.app import FrontikApplication

log = logging.getLogger('telemetry')
set_global_textmap(TraceContextTextMapPropagator())


def make_otel_provider(app: FrontikApplication) -> TracerProvider:
    resource = Resource(
        attributes={
            ResourceAttributes.SERVICE_NAME: app.app_name,
            ResourceAttributes.SERVICE_VERSION: app.application_version(),
            ResourceAttributes.HOST_NAME: options.node_name,
            ResourceAttributes.CLOUD_REGION: http_client_options.datacenter,
        },
    )
    provider = TracerProvider(
        resource=resource,
        id_generator=FrontikIdGenerator(),
        sampler=ParentBased(TraceIdRatioBased(options.opentelemetry_sampler_ratio)),
    )
    return provider


class FrontikServerInstrumentor(BaseInstrumentor):
    patched_handlers: list = []
    original_handler_new = None

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get('tracer_provider')
        self.tracer = trace.get_tracer(
            'frontik',
            '0.0.1',
            tracer_provider,
            schema_url='https://opentelemetry.io/schemas/1.11.0',
        )

    def _uninstrument(self, **kwargs):
        pass

    def instrumentation_dependencies(self):
        return []


class TelemetryIntegration(Integration):
    def __init__(self):
        self.aiohttp_instrumentor = aiohttp_client.AioHttpClientInstrumentor()
        self.frontik_instrumentor = FrontikServerInstrumentor()

    def initialize_app(self, frontik_app: FrontikApplication) -> Optional[Future]:
        if not options.opentelemetry_enabled:
            return None

        integrations_logger.info('start telemetry')
        provider = make_otel_provider(frontik_app)

        if options.opentelemetry_exporter_type == 'grpc':
            otlp_exporter: SpanExporter = GrpcExporter(endpoint=options.opentelemetry_collector_url, insecure=True)
        elif options.opentelemetry_exporter_type == 'http':
            otlp_exporter = HttpExporter(endpoint=options.opentelemetry_collector_url)
        else:
            raise ValueError(f'unknown opentelemetry_exporter_type = {options.opentelemetry_exporter_type}')
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(provider)

        self.aiohttp_instrumentor.instrument(request_hook=_client_request_hook, response_hook=_client_response_hook)
        self.frontik_instrumentor.instrument()
        frontik_app.otel_tracer = self.frontik_instrumentor.tracer  # type: ignore
        return None

    def deinitialize_app(self, app: FrontikApplication) -> None:
        if not options.opentelemetry_enabled:
            return

        integrations_logger.info('stop telemetry')
        self.frontik_instrumentor.uninstrument()
        self.aiohttp_instrumentor.uninstrument()
        return


def _client_request_hook(span: Span, params: aiohttp.TraceRequestStartParams) -> None:
    if not span or not span.is_recording():
        return

    request: RequestBuilder = current_client_request.get(None)
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
    if OUTER_TIMEOUT_MS_HEADER in request.headers:
        span.set_attribute('http.request.original.timeout', request.headers[OUTER_TIMEOUT_MS_HEADER])
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
    response_status_code: int = current_client_request_status.get(None)
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
                raise Exception('bad request_id')

            if len(request_id) < 32:
                log.debug('request_id = %s is less than 32 characters. Generating random trace_id', request_id)
                return random.getrandbits(128)

            return int(request_id[:32], 16)
        except Exception:
            log.debug('request_id = %s is not valid hex-format. Generating random trace_id', request_id)
        return random.getrandbits(128)
