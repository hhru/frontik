from frontik.app import FrontikApplication
from frontik.options import options


# ============================================
# test middleware

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Any
import time
import asyncio
from frontik.json_builder import JsonBuilder



class FphLuxMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        print('FphLuxMiddleware start')
        response = await call_next(request)
        print('FphLuxMiddleware done')
        return response

# ============================================
# telemetry mock

from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ReadableSpan, SpanExporter, SpanExportResult
from collections.abc import Sequence
from frontik.integrations.telemetry import make_otel_provider


class MockExporter(SpanExporter):
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            if span.kind == trace.SpanKind.SERVER:
                parent = None if span.parent is None else span.parent.span_id
                print(f'MockExporter export:{span.kind}, t_id: {span.context.trace_id}, s_id: {span.context.span_id}, '
                      f'parent_t_id: {parent}, ruchka: {span.attributes["http.target"]}')
            elif span.kind == trace.SpanKind.CLIENT:
                parent = None if span.parent is None else span.parent.span_id
                print(f'MockExporter export:{span.kind}, t_id: {span.context.trace_id}, s_id: {span.context.span_id}, '
                      f'parent_t_id: {parent}, ruchka: {span.attributes["http.url"]}')
            else:
                print(f'MockExporter export: unknown kind -- {span.kind}')

        return SpanExportResult.SUCCESS

    def shutdown(self):
        print('MockExporter shutdown')
        return None

    def force_flush(self, *args, **kwargs) -> bool:
        print('MockExporter force_flush')
        return True

# ============================================


class ExampleApplication(FrontikApplication):
    def __init__(self):
        super().__init__()
        # self.asgi_app.add_middleware(FphLuxMiddleware)

        # telemetry mock
        provider = make_otel_provider(self)
        batch_span_processor = BatchSpanProcessor(
            MockExporter(),
            max_queue_size=1,
            schedule_delay_millis=0.01,
            max_export_batch_size=1,
            export_timeout_millis=0,
        )
        provider.add_span_processor(batch_span_processor)
        trace.set_tracer_provider(provider)

    def application_version(self):
        return 123
