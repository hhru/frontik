import logging
import random
from asyncio import Future
from typing import Optional
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation import tornado
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider, IdGenerator
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.util.http import ExcludeList

from frontik import request_context
from frontik.integrations import Integration, integrations_logger
from frontik.options import options

log = logging.getLogger('telemetry')
# change log-level, because mainly detach context produce exception on Tornado 5. Will be deleted, when up Tornado to 6
logging.getLogger('opentelemetry.context').setLevel(logging.CRITICAL)
set_global_textmap(TraceContextTextMapPropagator())

tornado._excluded_urls = ExcludeList(list(tornado._excluded_urls._excluded_urls) + ['/status'])


class TelemetryIntegration(Integration):
    def __init__(self):
        self.instrumentation = None

    def initialize_app(self, app) -> Optional[Future]:
        if not options.opentelemetry_enabled:
            return

        integrations_logger.info('start telemetry')

        resource = Resource(attributes={
            ResourceAttributes.SERVICE_NAME: options.app,
            ResourceAttributes.SERVICE_VERSION: app.application_version(),
            ResourceAttributes.HOST_NAME: options.node_name,
            ResourceAttributes.CLOUD_REGION: options.datacenter,
        })
        otlp_exporter = OTLPSpanExporter(endpoint=options.opentelemetry_collector_url, insecure=True)

        provider = TracerProvider(resource=resource,
                                  id_generator=FrontikIdGenerator(),
                                  sampler=ParentBased(TraceIdRatioBased(options.opentelemetry_sampler_ratio)))

        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(provider)

        self.instrumentation = tornado.TornadoInstrumentor()
        self.instrumentation.instrument(
            server_request_hook=_server_request_hook,
            client_request_hook=_client_request_hook,
        )

    def deinitialize_app(self, app) -> Optional[Future]:
        if not options.opentelemetry_enabled:
            return

        integrations_logger.info('stop telemetry')
        self.instrumentation.uninstrument()

    def initialize_handler(self, handler):
        pass


def _server_request_hook(span, handler):
    span.update_name(f'{request_context.get_handler_name()}.{handler.request.method.lower()}_page')
    span.set_attribute(SpanAttributes.HTTP_TARGET, handler.request.uri)


def _client_request_hook(span, request):
    upstream_datacenter = getattr(request, 'upstream_datacenter', None)
    upstream_name = getattr(request, 'upstream_name', None)
    if upstream_name is None:
        upstream_name = get_netloc(request.url)

    span.update_name(' '.join((el for el in [request.method, upstream_name] if el)))
    span.set_attribute('http.request.timeout', request.request_timeout * 1000)
    if upstream_datacenter is not None:
        span.set_attribute('http.request.cloud.region', upstream_datacenter)


def get_netloc(url):
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
            if len(request_id) < 32:
                log.debug(f'request_id = {request_id} is less than 32 characters. Generating random trace_id ')
                return random.getrandbits(128)

            request_id = int(request_id[:32], 16)
            return request_id
        except Exception:
            log.debug(f'request_id = {request_id} is not valid hex-format. Generating random trace_id')
        return random.getrandbits(128)
