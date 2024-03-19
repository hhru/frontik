import unittest
from collections.abc import Sequence
from typing import Any, Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ReadableSpan, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.semconv.resource import ResourceAttributes
from tornado.httputil import HTTPServerRequest
from tornado.ioloop import IOLoop
from tornado.testing import gen_test

from frontik import request_context
from frontik.app import FrontikApplication
from frontik.handler import PageHandler, router
from frontik.integrations.telemetry import FrontikIdGenerator, get_netloc
from frontik.options import options
from frontik.testing import FrontikTestCase
from tests import FRONTIK_ROOT


class TestTelemetry(unittest.TestCase):
    def setUp(self) -> None:
        self.trace_id_generator = FrontikIdGenerator()

    def test_generate_trace_id_with_none_request_id(self) -> None:
        trace_id = self.trace_id_generator.generate_trace_id()
        self.assertIsNotNone(trace_id)

    def test_generate_trace_id_with_hex_request_id(self) -> None:
        with request_context.request_context(HTTPServerRequest(), '163897206709842601f90a070699ac44'):
            trace_id = self.trace_id_generator.generate_trace_id()
            self.assertEqual('0x163897206709842601f90a070699ac44', hex(trace_id))

    def test_generate_trace_id_with_no_hex_request_id(self) -> None:
        with request_context.request_context(HTTPServerRequest(), 'non-hex-string-1234'):
            trace_id = self.trace_id_generator.generate_trace_id()
            self.assertIsNotNone(trace_id)

    def test_generate_trace_id_with_no_str_request_id(self) -> None:
        with request_context.request_context(HTTPServerRequest(), 12345678910):  # type: ignore
            trace_id = self.trace_id_generator.generate_trace_id()
            self.assertIsNotNone(trace_id)

    def test_generate_trace_id_with_hex_request_id_and_postfix(self) -> None:
        with request_context.request_context(
            HTTPServerRequest(),
            '163897206709842601f90a070699ac44_some_postfix_string',
        ):
            trace_id = self.trace_id_generator.generate_trace_id()
            self.assertEqual('0x163897206709842601f90a070699ac44', hex(trace_id))

    def test_generate_trace_id_with_no_hex_request_id_in_first_32_characters(self) -> None:
        with request_context.request_context(
            HTTPServerRequest(),
            '16389720670_NOT_HEX_9842601f90a070699ac44_some_postfix_string',
        ):
            trace_id = self.trace_id_generator.generate_trace_id()
            self.assertIsNotNone(trace_id)
            self.assertNotEqual('0x16389720670_NOT_HEX_9842601f90a0', hex(trace_id))

    def test_generate_trace_id_with_request_id_len_less_32_characters(self) -> None:
        with request_context.request_context(HTTPServerRequest(), '163897206'):
            trace_id = self.trace_id_generator.generate_trace_id()
            self.assertIsNotNone(trace_id)
            self.assertNotEqual('0x163897206', hex(trace_id))

    def test_get_netloc(self) -> None:
        self.assertEqual('balancer:7000', get_netloc('balancer:7000/xml/get-article/'))
        self.assertEqual('balancer:7000', get_netloc('//balancer:7000/xml/get-article/'))
        self.assertEqual('balancer:7000', get_netloc('https://balancer:7000/xml/get-article/'))
        self.assertEqual('hh.ru', get_netloc('https://hh.ru'))
        self.assertEqual('ftp:', get_netloc('ftp://hh.ru'))


class PageA(PageHandler):
    @router.get()
    async def get_page(self):
        res = await self.get_url(self.request.host, '/page_b')
        self.json.put(res)


class PageB(PageHandler):
    @router.get()
    async def get_page(self):
        self.json.put({})


def make_otel_provider() -> TracerProvider:
    resource = Resource(
        attributes={
            ResourceAttributes.SERVICE_NAME: options.app,  # type: ignore
            ResourceAttributes.SERVICE_VERSION: '1.2.3',
            ResourceAttributes.HOST_NAME: options.node_name,
            ResourceAttributes.CLOUD_REGION: 'test',
        },
    )
    provider = TracerProvider(
        resource=resource,
        id_generator=FrontikIdGenerator(),
        sampler=ParentBased(TraceIdRatioBased(options.opentelemetry_sampler_ratio)),
    )
    return provider


SPAN_STORAGE: list[ReadableSpan] = []


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


class TestFrontikTesting(FrontikTestCase):
    def setUp(self) -> None:
        options.consul_enabled = False
        options.opentelemetry_enabled = True
        options.opentelemetry_sampler_ratio = 1

        test_exporter = TestExporter()
        provider = make_otel_provider()
        self.batch_span_processor = BatchSpanProcessor(test_exporter)
        provider.add_span_processor(self.batch_span_processor)
        trace.set_tracer_provider(provider)

        super().setUp()

    def get_app(self):
        class TestApplication(FrontikApplication):
            def application_urls(self):
                return [('/page_a', PageA), ('/page_b', PageB)]

        app = TestApplication(app='test_app', app_root=FRONTIK_ROOT)
        IOLoop.current().run_sync(app.init)
        return app

    @gen_test
    async def test_parent_span(self) -> None:
        url = self.get_url('/page_a')
        await self.http_client.fetch(url)
        self.batch_span_processor.force_flush()
        assert len(SPAN_STORAGE) == 3
        client_a_span = find_span('http.request.cloud.region', 'externalRequest')
        server_b_span = find_span('http.target', '/page_b')
        SPAN_STORAGE.clear()

        assert client_a_span is not None
        assert client_a_span.parent is not None
        assert server_b_span is not None
        assert server_b_span.parent is not None
