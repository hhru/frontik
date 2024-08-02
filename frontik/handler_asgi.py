from __future__ import annotations

import http.client
import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

from fastapi.routing import APIRoute
from tornado import httputil
from tornado.httputil import HTTPHeaders, HTTPServerRequest

from frontik import media_types, request_context
from frontik.debug import DebugMode, DebugTransform
from frontik.handler import PageHandler, get_default_headers, log_request
from frontik.handler_active_limit import request_limiter
from frontik.json_builder import JsonBuilder
from frontik.routing import find_route, get_allowed_methods, method_not_allowed_router, not_found_router

if TYPE_CHECKING:
    from frontik.app import FrontikApplication, FrontikAsgiApp

CHARSET = 'utf-8'
log = logging.getLogger('handler')


async def serve_request(
    frontik_app: FrontikApplication,
    tornado_request: HTTPServerRequest,
    asgi_app: FrontikAsgiApp,
) -> tuple[int, str, HTTPHeaders, bytes]:
    with request_limiter(frontik_app.statsd_client) as accepted:
        log.info('requested url: %s', tornado_request.uri)
        if not accepted:
            log_request(tornado_request, http.client.SERVICE_UNAVAILABLE)
            return make_not_accepted_response()

        debug_mode = make_debug_mode(frontik_app, tornado_request)
        if debug_mode.auth_failed():
            assert debug_mode.failed_auth_header is not None
            log_request(tornado_request, http.client.UNAUTHORIZED)
            return make_debug_auth_failed_response(debug_mode.failed_auth_header)

        assert tornado_request.method is not None

        route, page_cls, path_params = find_route(tornado_request.path, tornado_request.method)
        if route is None and tornado_request.method == 'HEAD':
            route, page_cls, path_params = find_route(tornado_request.path, 'GET')

        data: bytes

        if route is None:
            status, reason, headers, data = await make_not_found_response(
                frontik_app, asgi_app, tornado_request, debug_mode
            )
        else:
            status, reason, headers, data = await execute_page(
                frontik_app, asgi_app, tornado_request, route, page_cls, path_params, debug_mode
            )

        if debug_mode.enabled:
            debug_transform = DebugTransform(frontik_app, debug_mode)
            status, headers, data = debug_transform.transform_chunk(tornado_request, status, headers, data)
            reason = httputil.responses.get(status, 'Unknown')

        log_request(tornado_request, status)
        return status, reason, headers, data


async def execute_page(
    frontik_app: FrontikApplication,
    asgi_app: FrontikAsgiApp,
    tornado_request: HTTPServerRequest,
    route: APIRoute,
    page_cls: type[PageHandler] | None,
    path_params: dict,
    debug_mode: DebugMode,
) -> tuple[int, str, HTTPHeaders, bytes]:
    request_context.set_handler_name(f'{route.endpoint.__module__}.{route.endpoint.__name__}')

    if page_cls is not None:
        return await execute_tornado_page(frontik_app, tornado_request, route, page_cls, path_params, debug_mode)

    result: dict = {'headers': get_default_headers()}
    scope, receive, send = convert_tornado_request_to_asgi(
        frontik_app, tornado_request, route, path_params, debug_mode, result
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
    asgi_app: FrontikAsgiApp,
    tornado_request: httputil.HTTPServerRequest,
    debug_mode: DebugMode,
) -> tuple[int, str, HTTPHeaders, bytes]:
    allowed_methods = get_allowed_methods(tornado_request.path)
    default_headers = get_default_headers()
    headers: Any

    if allowed_methods and len(method_not_allowed_router.routes) != 0:
        status, _, headers, data = await execute_page(
            frontik_app,
            asgi_app,
            tornado_request,
            method_not_allowed_router.routes[0],  # type: ignore
            method_not_allowed_router._cls,
            {'allowed_methods': allowed_methods},
            debug_mode,
        )
    elif allowed_methods:
        status = 405
        headers = {'Allow': ', '.join(allowed_methods)}
        data = b''
    elif len(not_found_router.routes) != 0:
        status, _, headers, data = await execute_page(
            frontik_app,
            asgi_app,
            tornado_request,
            not_found_router.routes[0],  # type: ignore
            not_found_router._cls,
            {},
            debug_mode,
        )
    else:
        status, headers, data = build_error_data(404, 'Not Found')

    default_headers.update(headers)

    reason = httputil.responses.get(status, 'Unknown')
    return status, reason, HTTPHeaders(headers), data


def make_debug_mode(frontik_app: FrontikApplication, tornado_request: HTTPServerRequest) -> DebugMode:
    if hasattr(frontik_app, 'make_debug_mode'):
        return frontik_app.make_debug_mode(tornado_request)
    return DebugMode(tornado_request)


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
    route: APIRoute,
    page_cls: type[PageHandler],
    path_params: dict[str, str],
    debug_mode: DebugMode,
) -> tuple[int, str, HTTPHeaders, bytes]:
    handler: PageHandler = page_cls(frontik_app, tornado_request, route, debug_mode, path_params)
    return await handler.execute()


def convert_tornado_request_to_asgi(
    frontik_app: FrontikApplication,
    tornado_request: httputil.HTTPServerRequest,
    route: APIRoute,
    path_params: dict[str, str],
    debug_mode: DebugMode,
    result: dict[str, Any],
) -> tuple[dict, Callable, Callable]:
    headers = [
        (header.encode(CHARSET).lower(), value.encode(CHARSET))
        for header in tornado_request.headers
        for value in tornado_request.headers.get_list(header)
    ]

    json_builder = JsonBuilder()

    scope = {
        'type': tornado_request.protocol,
        'http_version': tornado_request.version,
        'path': tornado_request.path,
        'method': tornado_request.method,
        'query_string': tornado_request.query.encode(CHARSET),
        'headers': headers,
        'client': (tornado_request.remote_ip, 0),
        'route': route,
        'path_params': path_params,
        'http_client_factory': frontik_app.http_client_factory,
        'debug_enabled': debug_mode.enabled,
        'pass_debug': debug_mode.pass_debug,
        'start_time': tornado_request._start_time,
        'json_builder': json_builder,
    }

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
