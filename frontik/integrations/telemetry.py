from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from http_client import client_request_context, response_status_code_context
from http_client.options import options as http_client_options
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation import aiohttp_client, tornado
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import IdGenerator, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.util.http import ExcludeList

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
# change log-level, because mainly detach context produce exception on Tornado 5. Will be deleted, when up Tornado to 6
logging.getLogger('opentelemetry.context').setLevel(logging.CRITICAL)
set_global_textmap(TraceContextTextMapPropagator())

tornado._excluded_urls = ExcludeList([*list(tornado._excluded_urls._excluded_urls), '/status'])


class TelemetryIntegration(Integration):
    def __init__(self):
        self.aiohttp_instrumentor = aiohttp_client.AioHttpClientInstrumentor()
        self.tornado_instrumentor = tornado.TornadoInstrumentor()

    def initialize_app(self, app: FrontikApplication) -> Future | None:
        if not options.opentelemetry_enabled:
            return None

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

        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(provider)

        self.aiohttp_instrumentor.instrument(request_hook=_client_request_hook, response_hook=_client_response_hook)

        self.tornado_instrumentor.instrument(
            server_request_hook=_server_request_hook,
        )

        return None

    def deinitialize_app(self, app: FrontikApplication) -> Future | None:
        if not options.opentelemetry_enabled:
            return None

        integrations_logger.info('stop telemetry')
        self.aiohttp_instrumentor.uninstrument()
        self.tornado_instrumentor.uninstrument()
        return None

    def initialize_handler(self, handler):
        pass


def _server_request_hook(span, handler):
    span.update_name(f'{request_context.get_handler_name()}.{handler.request.method.lower()}_page')
    span.set_attribute(SpanAttributes.HTTP_TARGET, handler.request.uri)


def _client_request_hook(span: Span, params: aiohttp.TraceRequestStartParams) -> None:
    if not span or not span.is_recording():
        return

    request: RequestBuilder = client_request_context.get(None)
    if request is None:
        return

    upstream_datacenter = getattr(request, 'upstream_datacenter', None)
    upstream_name = getattr(request, 'upstream_name', None)
    if upstream_name is None:
        upstream_name = get_netloc(request.url)

    span.update_name(' '.join(el for el in [request.method, upstream_name] if el))
    span.set_attribute(SpanAttributes.PEER_SERVICE, upstream_name)
    span.set_attribute('http.request.timeout', request.request_timeout * 1000)
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
