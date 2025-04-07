from frontik.app import FrontikApplication
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ReadableSpan, SpanExporter, SpanExportResult
from collections.abc import Sequence
from opentelemetry import trace
from frontik.app_integrations.telemetry import make_otel_provider


BATCH_SPAN_PROCESSOR: list[BatchSpanProcessor] = []


class StubExporter(SpanExporter):
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, *args, **kwargs):
        pass


class ExampleApplication(FrontikApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        stub_exporter = StubExporter()
        provider = make_otel_provider(self)
        batch_span_processor = BatchSpanProcessor(stub_exporter)
        provider.add_span_processor(batch_span_processor)
        trace.set_tracer_provider(provider)
