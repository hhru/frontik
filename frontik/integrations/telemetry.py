from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

import opentelemetry.instrumentation.fastapi
from http_client import client_request_context, response_status_code_context
from http_client.options import options as http_client_options
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation import aiohttp_client, fastapi
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import IdGenerator, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import SpanKind
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from starlette.types import Scope

from frontik import request_context
from frontik.integrations import Integration, integrations_logger
from frontik.options import options

if TYPE_CHECKING:
    from asyncio import Future

    import aiohttp
    from http_client.request_response import RequestBuilder
    from opentelemetry.trace import Span

    from frontik.app import FrontikApplication

log = logging.getLogger('telemetry')
set_global_textmap(TraceContextTextMapPropagator())


class FrontikSpanProcessor(BatchSpanProcessor):
    def on_end(self, span: ReadableSpan) -> None:
        if (
            span.kind == SpanKind.INTERNAL
            and span.attributes
            and (
                span.attributes.get('type', None)
                in ('http.request', 'http.response.start', 'http.disconnect', 'http.response.body')
            )
        ):
            return
        super().on_end(span=span)


def monkey_patch_route_details(scope: Scope) -> tuple:
    route = scope['path']
    span_name = route or scope.get('method', '')
    attributes = {}
    if route:
        attributes[SpanAttributes.HTTP_ROUTE] = route
    return span_name, attributes


class TelemetryIntegration(Integration):
    def __init__(self):
        self.aiohttp_instrumentor = aiohttp_client.AioHttpClientInstrumentor()

    def initialize_app(self, app: FrontikApplication) -> Optional[Future]:
        if not options.opentelemetry_enabled:
            return None

        opentelemetry.instrumentation.fastapi._get_route_details = monkey_patch_route_details

        integrations_logger.info('start telemetry')

        resource = Resource(
            attributes={
                ResourceAttributes.SERVICE_NAME: options.app,  # type: ignore
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

        provider.add_span_processor(FrontikSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(provider)

        self.aiohttp_instrumentor.instrument(request_hook=_client_request_hook, response_hook=_client_response_hook)

        fastapi.FastAPIInstrumentor.instrument_app(
            app.fastapi_app, server_request_hook=_server_request_hook, excluded_urls='/status'
        )

        return None

    def deinitialize_app(self, app: FrontikApplication) -> Optional[Future]:
        if not options.opentelemetry_enabled:
            return None

        integrations_logger.info('stop telemetry')
        self.aiohttp_instrumentor.uninstrument()
        fastapi.FastAPIInstrumentor.uninstrument_app(app.fastapi_app)
        return None

    def initialize_handler(self, handler):
        pass


def _server_request_hook(span: Span, scope: dict) -> None:
    span.set_attribute(SpanAttributes.HTTP_TARGET, scope['path'])


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
