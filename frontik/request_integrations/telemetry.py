from frontik.request_integrations.integrations_dto import IntegrationDto
from frontik.options import options
from contextlib import contextmanager
from time import time_ns

from opentelemetry import trace
from opentelemetry.instrumentation.utils import _start_internal_or_server_span
from opentelemetry.propagators import textmap
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.util.http import get_traced_request_attrs
from opentelemetry.instrumentation.utils import extract_attributes_from_object
from opentelemetry.util.http import OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST
from opentelemetry.util.http import normalise_request_header_name
from opentelemetry.util.http import get_custom_headers
from opentelemetry.instrumentation.utils import http_status_to_status_code
from opentelemetry.util.http import OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE
from opentelemetry.util.http import normalise_response_header_name
from opentelemetry.trace.status import Status, StatusCode
from tornado import httputil
from tornado.httputil import HTTPServerRequest
from frontik import request_context

_traced_request_attrs = get_traced_request_attrs('TORNADO')
_excluded_urls = ['/status']


def _start_span(tracer, tornado_request) -> trace.span.Span:
    span, token = _start_internal_or_server_span(
        tracer=tracer,
        span_name=_get_default_span_name(tornado_request),
        start_time=time_ns(),
        context_carrier=tornado_request.headers,
        context_getter=textmap.default_getter,
    )

    if span.is_recording():
        attributes = _get_attributes_from_request(tornado_request)
        for key, value in attributes.items():
            span.set_attribute(key, value)
        if span.is_recording() and span.kind == trace.SpanKind.SERVER:
            custom_attributes = _collect_custom_request_headers_attributes(tornado_request.headers)
            if len(custom_attributes) > 0:
                span.set_attributes(custom_attributes)

    return span


def _get_default_span_name(tornado_request):
    path = tornado_request.path
    method = tornado_request.method
    if method and path:
        return f'{method} {path}'
    return f'{method}'


def _get_attributes_from_request(tornado_request: HTTPServerRequest):
    attrs = {
        SpanAttributes.HTTP_METHOD: tornado_request.method,
        SpanAttributes.HTTP_SCHEME: tornado_request.protocol,
        SpanAttributes.HTTP_HOST: tornado_request.host,
        SpanAttributes.HTTP_TARGET: tornado_request.uri,
    }

    if tornado_request.remote_ip:
        attrs[SpanAttributes.HTTP_CLIENT_IP] = tornado_request.remote_ip
        if hasattr(tornado_request.connection, 'context') and getattr(
            tornado_request.connection.context, '_orig_remote_ip', None
        ):
            attrs[SpanAttributes.NET_PEER_IP] = tornado_request.connection.context._orig_remote_ip

    return extract_attributes_from_object(tornado_request, _traced_request_attrs, attrs)


def _collect_custom_request_headers_attributes(request_headers):
    custom_request_headers_name = get_custom_headers(OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST)
    attributes = {}
    for header_name in custom_request_headers_name:
        header_values = request_headers.get(header_name)
        if header_values:
            key = normalise_request_header_name(header_name.lower())
            attributes[key] = [header_values]
    return attributes


def _finish_span(span, dto: IntegrationDto, tornado_request: HTTPServerRequest):
    if not span.is_recording():
        return

    status_code = dto.response.status_code
    resp_headers = dto.response.headers

    span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status_code)
    span.set_attribute(SpanAttributes.USER_AGENT_ORIGINAL, tornado_request.headers.get('User-Agent', 'noUserAgent'))
    if hasattr(tornado_request, '_path_format'):
        span.set_attribute(SpanAttributes.HTTP_ROUTE, getattr(tornado_request, '_path_format'))
    if (handler_name := request_context.get_handler_name()) is not None:
        method_path, method_name = handler_name.rsplit('.', 1)
        span.update_name(f'{method_path}.{method_name}')
        span.set_attribute(SpanAttributes.CODE_FUNCTION, method_name)
        span.set_attribute(SpanAttributes.CODE_NAMESPACE, method_path)

    otel_status_code = http_status_to_status_code(status_code, server_span=True)
    otel_status_description = None
    if otel_status_code is StatusCode.ERROR:
        otel_status_description = httputil.responses.get(status_code, 'Unknown')
    span.set_status(
        Status(
            status_code=otel_status_code,
            description=otel_status_description,
        )
    )
    if span.is_recording() and span.kind == trace.SpanKind.SERVER:
        custom_attributes = _collect_custom_response_headers_attributes(resp_headers)
        if len(custom_attributes) > 0:
            span.set_attributes(custom_attributes)


def _collect_custom_response_headers_attributes(response_headers):
    custom_response_headers_name = get_custom_headers(OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE)
    attributes = {}
    for header_name in custom_response_headers_name:
        header_values = response_headers.get(header_name)
        if header_values:
            key = normalise_response_header_name(header_name.lower())
            attributes[key] = [header_values]
    return attributes


@contextmanager
def otel_instrumentation_ctx(frontik_app, tornado_request):
    if not options.opentelemetry_enabled or tornado_request.path in _excluded_urls:
        yield IntegrationDto()
        return

    span = _start_span(frontik_app.otel_tracer, tornado_request)

    with trace.use_span(span, end_on_exit=True):
        dto = IntegrationDto()
        try:
            yield dto
        finally:
            _finish_span(span, dto, tornado_request)
