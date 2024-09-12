from __future__ import annotations

import asyncio
import http.client
import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Optional

from tornado import httputil
from tornado.httputil import HTTPHeaders, HTTPServerRequest

from frontik import media_types, request_context
from frontik.debug import DebugMode, DebugTransform
from frontik.handler import PageHandler, get_default_headers, log_request
from frontik.handler_active_limit import request_limiter
from frontik.http_status import CLIENT_CLOSED_REQUEST
from frontik.json_builder import JsonBuilder
from frontik.options import options
from frontik.routing import find_route, get_allowed_methods, method_not_allowed_router, not_found_router
from frontik.util import check_request_id, generate_uniq_timestamp_request_id
from frontik.integrations.telemetry import experimental_instrumentor
from frontik.integrations.telemetry_instr_frontik import otel_instrumentation_ctx

if TYPE_CHECKING:
    from frontik.app import FrontikApplication, FrontikAsgiApp

CHARSET = 'utf-8'
log = logging.getLogger('handler')


async def serve_tornado_request(
    frontik_app: FrontikApplication,
    asgi_app: FrontikAsgiApp,
    tornado_request: httputil.HTTPServerRequest,
) -> None:
    request_id = tornado_request.headers.get('X-Request-Id') or generate_uniq_timestamp_request_id()
    if options.validate_request_id:
        check_request_id(request_id)
    tornado_request.request_id = request_id  # type: ignore

    with request_context.request_context(request_id), otel_instrumentation_ctx(experimental_instrumentor, tornado_request) as otel_resul:
        log.info('requested url: %s', tornado_request.uri)

        process_request_task = asyncio.create_task(process_request(frontik_app, asgi_app, tornado_request))

        assert tornado_request.connection is not None
        tornado_request.connection.set_close_callback(  # type: ignore
            partial(_on_connection_close, tornado_request, process_request_task, otel_resul)
        )

        status, reason, headers, data = await process_request_task

        assert tornado_request.connection is not None
        tornado_request.connection.set_close_callback(None)  # type: ignore

        otel_resul['status'] = status
        otel_resul['headers'] = headers

        start_line = httputil.ResponseStartLine('', status, reason)
        future = tornado_request.connection.write_headers(start_line, headers, data)
        log_request(tornado_request, status)

        tornado_request.connection.finish()
        return await future


async def process_request(
    frontik_app: FrontikApplication,
    asgi_app: FrontikAsgiApp,
    tornado_request: httputil.HTTPServerRequest,
) -> tuple[int, str, HTTPHeaders, bytes]:
    with request_limiter(frontik_app.statsd_client) as accepted:
        if not accepted:
            status, reason, headers, data = make_not_accepted_response()
        else:
            status, reason, headers, data = await execute_page(frontik_app, asgi_app, tornado_request)
            headers.add(
                'Server-Timing', f'frontik;desc="frontik execution time";dur={tornado_request.request_time()!s}'
            )

        return status, reason, headers, data


async def execute_page(
    frontik_app: FrontikApplication,
    asgi_app: FrontikAsgiApp,
    tornado_request: HTTPServerRequest,
) -> tuple[int, str, HTTPHeaders, bytes]:
    debug_mode = make_debug_mode(frontik_app, tornado_request)
    if debug_mode.auth_failed():
        assert debug_mode.failed_auth_header is not None
        return make_debug_auth_failed_response(debug_mode.failed_auth_header)

    assert tornado_request.method is not None
    assert tornado_request.protocol == 'http'

    scope = find_route(tornado_request.path, tornado_request.method)
    data: bytes

    if scope['route'] is None:
        status, reason, headers, data = await make_not_found_response(frontik_app, tornado_request, debug_mode)
    elif scope['page_cls'] is not None:
        status, reason, headers, data = await execute_tornado_page(frontik_app, tornado_request, scope, debug_mode)
    else:
        status, reason, headers, data = await execute_asgi_page(
            asgi_app,
            tornado_request,
            scope,
            debug_mode,
        )

    if debug_mode.enabled:
        debug_transform = DebugTransform(frontik_app, debug_mode)
        status, headers, data = debug_transform.transform_chunk(tornado_request, status, headers, data)
        reason = httputil.responses.get(status, 'Unknown')

    return status, reason, headers, data


async def execute_asgi_page(
    asgi_app: FrontikAsgiApp,
    tornado_request: HTTPServerRequest,
    scope: dict,
    debug_mode: DebugMode,
) -> tuple[int, str, HTTPHeaders, bytes]:
    request_context.set_handler_name(scope['route'])
    result: dict = {'headers': get_default_headers()}
    scope, receive, send = convert_tornado_request_to_asgi(
        asgi_app,
        tornado_request,
        scope,
        debug_mode,
        result,
    )
    await asgi_app(scope, receive, send)

    status: int = result['status']
    reason = httputil.responses.get(status, 'Unknown')
    headers = HTTPHeaders(result['headers'])
    data = result['data']

    if not scope['json_builder'].is_empty():
        if data != b'null':
            raise RuntimeError('Cant have "return" and "json.put" at the same time')

        headers['Content-Type'] = media_types.APPLICATION_JSON
        data = scope['json_builder'].to_bytes()
        headers['Content-Length'] = str(len(data))

    return status, reason, headers, data


async def make_not_found_response(
    frontik_app: FrontikApplication,
    tornado_request: httputil.HTTPServerRequest,
    debug_mode: DebugMode,
) -> tuple[int, str, HTTPHeaders, bytes]:
    allowed_methods = get_allowed_methods(tornado_request.path)
    default_headers = get_default_headers()
    headers: Any

    if allowed_methods and len(method_not_allowed_router.routes) != 0:
        status, _, headers, data = await execute_tornado_page(
            frontik_app,
            tornado_request,
            {
                'route': method_not_allowed_router.routes[0],
                'page_cls': method_not_allowed_router._cls,
                'path_params': {'allowed_methods': allowed_methods},
            },
            debug_mode,
        )
    elif allowed_methods:
        status = 405
        headers = {'Allow': ', '.join(allowed_methods)}
        data = b''
    elif len(not_found_router.routes) != 0:
        status, _, headers, data = await execute_tornado_page(
            frontik_app,
            tornado_request,
            {'route': not_found_router.routes[0], 'page_cls': not_found_router._cls, 'path_params': {}},
            debug_mode,
        )
    else:
        status, headers, data = build_error_data(404, 'Not Found')

    default_headers.update(headers)

    reason = httputil.responses.get(status, 'Unknown')
    return status, reason, HTTPHeaders(headers), data


def make_debug_mode(frontik_app: FrontikApplication, tornado_request: HTTPServerRequest) -> DebugMode:
    debug_mode = DebugMode(tornado_request)

    if not debug_mode.need_auth:
        return debug_mode

    if hasattr(frontik_app, 'require_debug_access'):
        frontik_app.require_debug_access(debug_mode, tornado_request)
    else:
        debug_mode.require_debug_access(tornado_request)

    return debug_mode


def make_debug_auth_failed_response(auth_header: str) -> tuple[int, str, HTTPHeaders, bytes]:
    status = http.client.UNAUTHORIZED
    reason = httputil.responses.get(status, 'Unknown')
    headers = get_default_headers()
    headers['WWW-Authenticate'] = auth_header

    return status, reason, HTTPHeaders(headers), b''


def make_not_accepted_response() -> tuple[int, str, HTTPHeaders, bytes]:
    status = http.client.SERVICE_UNAVAILABLE
    reason = httputil.responses.get(status, 'Unknown')
    headers = get_default_headers()
    return status, reason, HTTPHeaders(headers), b''


def build_error_data(
    status_code: int = 500, message: Optional[str] = 'Internal Server Error'
) -> tuple[int, dict, bytes]:
    headers = {'Content-Type': media_types.TEXT_HTML}
    data = f'<html><title>{status_code}: {message}</title><body>{status_code}: {message}</body></html>'.encode()
    return status_code, headers, data


async def execute_tornado_page(
    frontik_app: FrontikApplication,
    tornado_request: httputil.HTTPServerRequest,
    scope: dict,
    debug_mode: DebugMode,
) -> tuple[int, str, HTTPHeaders, bytes]:
    route, page_cls, path_params = scope['route'], scope['page_cls'], scope['path_params']
    request_context.set_handler_name(route)
    handler: PageHandler = page_cls(frontik_app, tornado_request, route, debug_mode, path_params)
    return await handler.execute()


def convert_tornado_request_to_asgi(
    asgi_app: FrontikAsgiApp,
    tornado_request: httputil.HTTPServerRequest,
    scope: dict,
    debug_mode: DebugMode,
    result: dict[str, Any],
) -> tuple[dict, Callable, Callable]:
    headers = [
        (header.encode(CHARSET).lower(), value.encode(CHARSET))
        for header in tornado_request.headers
        for value in tornado_request.headers.get_list(header)
    ]

    scope.update({
        'http_version': tornado_request.version,
        'query_string': tornado_request.query.encode(CHARSET),
        'headers': headers,
        'client': (tornado_request.remote_ip, 0),
        'http_client_factory': asgi_app.http_client_factory,
        'debug_mode': debug_mode,
        'start_time': tornado_request._start_time,
        'json_builder': JsonBuilder(),
    })

    async def receive():
        return {
            'body': tornado_request.body,
            'type': 'http.request',
            'more_body': False,
        }

    async def send(data):
        if data['type'] == 'http.response.start':
            result['status'] = data['status']
            for h in data['headers']:
                if len(h) == 2:
                    result['headers'][h[0].decode(CHARSET)] = h[1].decode(CHARSET)
        elif data['type'] == 'http.response.body':
            assert isinstance(data['body'], bytes)
            result['data'] = data['body']
        else:
            raise RuntimeError(f'Unsupported response type "{data["type"]}" for asgi app')

    return scope, receive, send


def _on_connection_close(tornado_request, process_request_task, otel_resul):
    otel_resul['status'] = CLIENT_CLOSED_REQUEST
    otel_resul['headers'] = httputil.HTTPHeaders()
    log_request(tornado_request, CLIENT_CLOSED_REQUEST)
    setattr(tornado_request, 'canceled', False)
    process_request_task.cancel()  # instantly kill serve_tornado_request with CanceledError
