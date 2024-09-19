from collections.abc import Sequence
from typing import Any, Optional

import pytest
from fastapi import Request
from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ReadableSpan, SpanExporter, SpanExportResult
from opentelemetry.semconv.trace import SpanAttributes

from frontik import request_context
from frontik.app import FrontikApplication
from frontik.app_integrations.telemetry import FrontikIdGenerator, get_netloc, make_otel_provider
from frontik.handler import PageHandler, get_current_handler
from frontik.options import options
from frontik.routing import plain_router
from frontik.testing import FrontikTestBase

dummy_request = Request({'type': 'http'})


class TestTelemetry:
    def setup_method(self) -> None:
        self.trace_id_generator = FrontikIdGenerator()

    def test_generate_trace_id_with_none_request_id(self) -> None:
        trace_id = self.trace_id_generator.generate_trace_id()
        assert trace_id is not None

    def test_generate_trace_id_with_hex_request_id(self) -> None:
        with request_context.request_context('163897206709842601f90a070699ac44'):
            trace_id = self.trace_id_generator.generate_trace_id()
            assert '0x163897206709842601f90a070699ac44' == hex(trace_id)

    def test_generate_trace_id_with_no_hex_request_id(self) -> None:
        with request_context.request_context('non-hex-string-1234'):
            trace_id = self.trace_id_generator.generate_trace_id()
            assert trace_id is not None

    def test_generate_trace_id_with_no_str_request_id(self) -> None:
        with request_context.request_context(12345678910):  # type: ignore
            trace_id = self.trace_id_generator.generate_trace_id()
            assert trace_id is not None

    def test_generate_trace_id_with_hex_request_id_and_postfix(self) -> None:
        with request_context.request_context('163897206709842601f90a070699ac44_some_postfix_string'):
            trace_id = self.trace_id_generator.generate_trace_id()
            assert '0x163897206709842601f90a070699ac44' == hex(trace_id)

    def test_generate_trace_id_with_no_hex_request_id_in_first_32_characters(self) -> None:
        with request_context.request_context('16389720670_NOT_HEX_9842601f90a070699ac44_some_postfix_string'):
            trace_id = self.trace_id_generator.generate_trace_id()
            assert trace_id is not None
            assert '0x16389720670_NOT_HEX_9842601f90a0' != hex(trace_id)

    def test_generate_trace_id_with_request_id_len_less_32_characters(self) -> None:
        with request_context.request_context('163897206'):
            trace_id = self.trace_id_generator.generate_trace_id()
            assert trace_id is not None
            assert '0x163897206' != hex(trace_id)

    def test_get_netloc(self) -> None:
        assert 'balancer:7000' == get_netloc('balancer:7000/xml/get-article/')
        assert 'balancer:7000' == get_netloc('//balancer:7000/xml/get-article/')
        assert 'balancer:7000' == get_netloc('https://balancer:7000/xml/get-article/')
        assert 'hh.ru' == get_netloc('https://hh.ru')
        assert 'ftp:' == get_netloc('ftp://hh.ru')


@plain_router.get('/page_a', cls=PageHandler)
async def get_page_a(handler=get_current_handler()):
    res = await handler.get_url(handler.get_header('host'), '/page_b')
    handler.json.put(res)


@plain_router.get('/page_b', cls=PageHandler)
async def get_page_b(handler=get_current_handler()):
    handler.json.put({})


SPAN_STORAGE: list[ReadableSpan] = []
BATCH_SPAN_PROCESSOR: list[BatchSpanProcessor] = []


def find_span(attr: str, value: Any) -> Optional[ReadableSpan]:
    return next(filter(lambda item: item.attributes.get(attr, None) == value, SPAN_STORAGE), None)  # type: ignore


class TestExporter(SpanExporter):
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        SPAN_STORAGE.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, *args, **kwargs):
        pass


class TestFrontikTesting(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        options.consul_enabled = False
        options.opentelemetry_enabled = True
        options.opentelemetry_sampler_ratio = 1

        app = FrontikApplication()

        test_exporter = TestExporter()
        provider = make_otel_provider(app)
        batch_span_processor = BatchSpanProcessor(test_exporter)
        provider.add_span_processor(batch_span_processor)
        trace.set_tracer_provider(provider)

        BATCH_SPAN_PROCESSOR.append(batch_span_processor)

        return app

    async def test_parent_span(self, frontik_app: FrontikApplication) -> None:
        await self.fetch('/page_a')
        BATCH_SPAN_PROCESSOR[0].force_flush()
        assert len(SPAN_STORAGE) == 4
        client_a_span = find_span('http.request.cloud.region', 'externalRequest')
        server_b_span = find_span('http.target', '/page_b')
        SPAN_STORAGE.clear()

        assert client_a_span is not None
        assert client_a_span.parent is not None
        assert server_b_span is not None
        assert server_b_span.parent is not None

        assert server_b_span.attributes is not None
        assert server_b_span.attributes.get(SpanAttributes.CODE_FUNCTION) == 'get_page_b'
        assert server_b_span.attributes.get(SpanAttributes.CODE_NAMESPACE) == 'tests.test_telemetry'
