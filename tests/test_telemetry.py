import asyncio
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Optional

import pytest
from fastapi import Request
from http_client.request_response import INSUFFICIENT_TIMEOUT
from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ReadableSpan, SpanExporter, SpanExportResult
from opentelemetry.semconv.trace import SpanAttributes

from frontik.app import FrontikApplication
from frontik.app_integrations.telemetry import FrontikIdGenerator, get_netloc, make_otel_provider
from frontik.dependencies import HttpClient
from frontik.options import options
from frontik.request_integrations.request_context import RequestContext, _request_context
from frontik.routing import router
from frontik.testing import FrontikTestBase

dummy_request = Request({'type': 'http'})


@contextmanager
def request_context(request_id: Optional[str]) -> Iterator:
    token = _request_context.set(RequestContext(request_id))
    try:
        yield
    finally:
        _request_context.reset(token)


class TestTelemetry:
    def setup_method(self) -> None:
        self.trace_id_generator = FrontikIdGenerator()

    def test_generate_trace_id_with_none_request_id(self) -> None:
        with request_context(None):
            trace_id = self.trace_id_generator.generate_trace_id()
            assert trace_id is not None

    def test_generate_trace_id_with_hex_request_id(self) -> None:
        with request_context('163897206709842601f90a070699ac44'):
            trace_id = self.trace_id_generator.generate_trace_id()
            assert hex(trace_id) == '0x163897206709842601f90a070699ac44'

    def test_generate_trace_id_with_no_hex_request_id(self) -> None:
        with request_context('non-hex-string-1234'):
            trace_id = self.trace_id_generator.generate_trace_id()
            assert trace_id is not None

    def test_generate_trace_id_with_hex_request_id_and_postfix(self) -> None:
        with request_context('163897206709842601f90a070699ac44_some_postfix_string'):
            trace_id = self.trace_id_generator.generate_trace_id()
            assert hex(trace_id) == '0x163897206709842601f90a070699ac44'

    def test_generate_trace_id_with_no_hex_request_id_in_first_32_characters(self) -> None:
        with request_context('16389720670_NOT_HEX_9842601f90a070699ac44_some_postfix_string'):
            trace_id = self.trace_id_generator.generate_trace_id()
            assert trace_id is not None
            assert hex(trace_id) != '0x16389720670_NOT_HEX_9842601f90a0'

    def test_generate_trace_id_with_request_id_len_less_32_characters(self) -> None:
        with request_context('163897206'):
            trace_id = self.trace_id_generator.generate_trace_id()
            assert trace_id is not None
            assert hex(trace_id) != '0x163897206'

    def test_get_netloc(self) -> None:
        assert get_netloc('balancer:7000/xml/get-article/') == 'balancer:7000'
        assert get_netloc('//balancer:7000/xml/get-article/') == 'balancer:7000'
        assert get_netloc('https://balancer:7000/xml/get-article/') == 'balancer:7000'
        assert get_netloc('https://hh.ru') == 'hh.ru'
        assert get_netloc('ftp://hh.ru') == 'ftp:'


@router.get('/page_a')
async def get_page_a(request: Request, http_client: HttpClient) -> None:
    await http_client.get_url(request.headers.get('host'), '/page_b?firstParam=1&secondParam=2')


@router.get('/long_otel_page')
async def long_otel_page() -> None:
    await asyncio.sleep(1)


@router.get('/page_b')
async def get_page_b() -> dict:
    await asyncio.sleep(0.1)
    return {}


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


class TestOtelSpans(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        options.consul_enabled = False
        options.opentelemetry_enabled = True
        options.opentelemetry_sampler_ratio = 1

        app = FrontikApplication(app_module_name=None)

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
        server_b_span = find_span('http.route', '/page_b')
        SPAN_STORAGE.clear()

        assert client_a_span is not None
        assert client_a_span.parent is not None
        assert server_b_span is not None
        assert server_b_span.parent is not None

        assert server_b_span.attributes is not None
        assert server_b_span.attributes.get(SpanAttributes.CODE_FUNCTION) == 'get_page_b'
        assert server_b_span.attributes.get(SpanAttributes.CODE_NAMESPACE) == 'tests.test_telemetry'
        assert server_b_span.attributes.get(SpanAttributes.USER_AGENT_ORIGINAL) == self.app.app_name
        assert server_b_span.attributes.get(SpanAttributes.HTTP_ROUTE) == '/page_b'
        assert server_b_span.attributes.get(SpanAttributes.HTTP_TARGET) == '/page_b?firstParam=1&secondParam=2'

    async def test_client_close_connection(self, frontik_app: FrontikApplication) -> None:
        await self.fetch('/long_otel_page', request_timeout=0.4)
        await asyncio.sleep(0.5)
        BATCH_SPAN_PROCESSOR[0].force_flush()
        assert len(SPAN_STORAGE) == 2
        server_span = find_span('http.route', '/long_otel_page')
        SPAN_STORAGE.clear()

        assert server_span is not None
        assert server_span.attributes is not None
        assert server_span.attributes.get(SpanAttributes.CODE_FUNCTION) == 'long_otel_page'
        assert server_span.attributes.get(SpanAttributes.CODE_NAMESPACE) == 'tests.test_telemetry'
        assert server_span.attributes.get(SpanAttributes.USER_AGENT_ORIGINAL) == 'test'
        assert server_span.attributes.get(SpanAttributes.HTTP_ROUTE) == '/long_otel_page'
        assert server_span.attributes.get(SpanAttributes.HTTP_TARGET) == '/long_otel_page'

    async def test_otel_http_client_hook(self, frontik_app: FrontikApplication) -> None:
        await self.fetch('/page_a', headers={'X-Outer-Timeout-Ms': '1200', 'X-Deadline-Timeout-Ms': '5'})
        BATCH_SPAN_PROCESSOR[0].force_flush()
        client_a_span = find_span('http.request.cloud.region', 'externalRequest')
        SPAN_STORAGE.clear()
        assert client_a_span is not None
        assert client_a_span.attributes is not None
        assert client_a_span.attributes.get(SpanAttributes.HTTP_STATUS_CODE) == INSUFFICIENT_TIMEOUT
