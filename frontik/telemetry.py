import logging
import random

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.tornado import TornadoInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider, IdGenerator
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from frontik import request_context

log = logging.getLogger('telemetry')
# change log-level, because mainly detach context produce exception on Tornado 5. Will be deleted, when up Tornado to 6
logging.getLogger('opentelemetry.context').setLevel(logging.CRITICAL)
set_global_textmap(TraceContextTextMapPropagator())


def _generate_telemetry_host(options) -> str:
    return f'{options.opentelemetry_collector_host}:{options.opentelemetry_collector_port}'


class Telemetry:
    def __init__(self, options):
        self.resource = Resource(attributes={
            'service.name': options.app
        })
        self.id_generator = FrontikIdGenerator()
        self.otlp_exporter = OTLPSpanExporter(endpoint=_generate_telemetry_host(options),
                                              insecure=True)
        self.batch_span_processor = BatchSpanProcessor(self.otlp_exporter)
        trace.set_tracer_provider(TracerProvider(resource=self.resource,
                                                 id_generator=self.id_generator,
                                                 sampler=TraceIdRatioBased(options.opentelemetry_sampler_ratio)))
        trace.get_tracer_provider().add_span_processor(self.batch_span_processor)

    def start_instrumentation(self):
        TornadoInstrumentor().instrument(
            # Will be removed, when releasing https://github.com/open-telemetry/opentelemetry-python-contrib/pull/812
            skip_dep_check=True,
            client_request_hook=_client_request_hook,
        )

    def stop_instrumentation(self):
        TornadoInstrumentor().uninstrument()


def _client_request_hook(span, request):
    span.update_name(request_context.get_handler_name())
    span.set_attribute("requestTimeout", request.request_timeout)
    span.set_attribute("connectTimeout", request.connect_timeout)


class FrontikIdGenerator(IdGenerator):

    def generate_span_id(self) -> int:
        return random.getrandbits(64)

    def generate_trace_id(self) -> int:
        try:
            request_id = int(request_context.get_request_id(), 16)
            return request_id
        except ValueError:
            log.debug('request_id is not valid hex-format. Generating random trace_id')
        return random.getrandbits(128)
