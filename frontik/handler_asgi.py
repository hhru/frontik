from __future__ import annotations

import asyncio
import http.client
import logging
from functools import partial
from typing import TYPE_CHECKING, Optional

from tornado import httputil
from tornado.httputil import HTTPServerRequest

from frontik import media_types, request_context
from frontik.debug import DebugMode, DebugTransform
from frontik.frontik_response import FrontikResponse
from frontik.handler import PageHandler, log_request
from frontik.handler_active_limit import request_limiter
from frontik.http_status import CLIENT_CLOSED_REQUEST
from frontik.options import options
from frontik.routing import find_route, get_allowed_methods, method_not_allowed_router, not_found_router
from frontik.util import check_request_id, generate_uniq_timestamp_request_id

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

    with request_context.request_context(request_id):
        log.info('requested url: %s', tornado_request.uri)

        process_request_task = asyncio.create_task(process_request(frontik_app, asgi_app, tornado_request))

        assert tornado_request.connection is not None
        tornado_request.connection.set_close_callback(  # type: ignore
            partial(_on_connection_close, tornado_request, process_request_task)
        )

        response = await process_request_task
        log_request(tornado_request, response.status_code)

        assert tornado_request.connection is not None
        tornado_request.connection.set_close_callback(None)  # type: ignore

        if getattr(tornado_request, 'canceled', False):
            return None

        if not response.data_written:
            start_line = httputil.ResponseStartLine('', response.status_code, response.reason)
            await tornado_request.connection.write_headers(start_line, response.headers, response.body)

        tornado_request.connection.finish()


async def process_request(
    frontik_app: FrontikApplication,
    asgi_app: FrontikAsgiApp,
    tornado_request: httputil.HTTPServerRequest,
) -> FrontikResponse:
    with request_limiter(frontik_app.statsd_client) as accepted:
        if not accepted:
            response = make_not_accepted_response()
        else:
            response = await execute_page(frontik_app, asgi_app, tornado_request)
            response.headers.add(
                'Server-Timing', f'frontik;desc="frontik execution time";dur={tornado_request.request_time()!s}'
            )

        return response


async def execute_page(
    frontik_app: FrontikApplication,
    asgi_app: FrontikAsgiApp,
    tornado_request: HTTPServerRequest,
) -> FrontikResponse:
    debug_mode = make_debug_mode(frontik_app, tornado_request)
    if debug_mode.auth_failed():
        assert debug_mode.failed_auth_header is not None
        return make_debug_auth_failed_response(debug_mode.failed_auth_header)

    assert tornado_request.method is not None
    assert tornado_request.protocol == 'http'

    scope = find_route(tornado_request.path, tornado_request.method)

    if scope['route'] is None:
        response = await make_not_found_response(frontik_app, tornado_request, debug_mode)
    elif scope['page_cls'] is not None:
        response = await execute_tornado_page(frontik_app, tornado_request, scope, debug_mode)
    else:
        response = await execute_asgi_page(asgi_app, tornado_request, scope, debug_mode)

    if debug_mode.enabled and not response.data_written:
        debug_transform = DebugTransform(frontik_app, debug_mode)
        response = debug_transform.transform_chunk(tornado_request, response)

    return response


async def execute_asgi_page(
    asgi_app: FrontikAsgiApp,
    tornado_request: HTTPServerRequest,
    scope: dict,
    debug_mode: DebugMode,
) -> FrontikResponse:
    request_context.set_handler_name(scope['route'])

    response = FrontikResponse(status_code=200)

    request_headers = [
        (header.encode(CHARSET).lower(), value.encode(CHARSET))
        for header in tornado_request.headers
        for value in tornado_request.headers.get_list(header)
    ]

    scope.update({
        'http_version': tornado_request.version,
        'query_string': tornado_request.query.encode(CHARSET),
        'headers': request_headers,
        'client': (tornado_request.remote_ip, 0),
        'http_client_factory': asgi_app.http_client_factory,
        'debug_mode': debug_mode,
        'start_time': tornado_request._start_time,
    })

    async def receive():
        await asyncio.sleep(0)
        return {
            'body': tornado_request.body,
            'type': 'http.request',
            'more_body': False,
        }

    async def send(data):
        assert tornado_request.connection is not None

        if data['type'] == 'http.response.start':
            response.status_code = int(data['status'])
            for h in data['headers']:
                if len(h) == 2:
                    response.headers.add(h[0].decode(CHARSET), h[1].decode(CHARSET))
        elif data['type'] == 'http.response.body':
            chunk = data['body']
            if debug_mode.enabled or not data.get('more_body'):
                response.body += chunk
            elif not response.data_written:
                await tornado_request.connection.write_headers(
                    start_line=httputil.ResponseStartLine('', response.status_code, response.reason),
                    headers=response.headers,
                    chunk=chunk,
                )
                response.data_written = True
            else:
                await tornado_request.connection.write(chunk)
        else:
            raise RuntimeError(f'Unsupported response type "{data["type"]}" for asgi app')

    await asgi_app(scope, receive, send)

    return response


async def make_not_found_response(
    frontik_app: FrontikApplication,
    tornado_request: httputil.HTTPServerRequest,
    debug_mode: DebugMode,
) -> FrontikResponse:
    allowed_methods = get_allowed_methods(tornado_request.path)

    if allowed_methods and len(method_not_allowed_router.routes) != 0:
        return await execute_tornado_page(
            frontik_app,
            tornado_request,
            {
                'route': method_not_allowed_router.routes[0],
                'page_cls': method_not_allowed_router._cls,
                'path_params': {'allowed_methods': allowed_methods},
            },
            debug_mode,
        )

    if allowed_methods:
        return FrontikResponse(status_code=405, headers={'Allow': ', '.join(allowed_methods)})

    if len(not_found_router.routes) != 0:
        return await execute_tornado_page(
            frontik_app,
            tornado_request,
            {'route': not_found_router.routes[0], 'page_cls': not_found_router._cls, 'path_params': {}},
            debug_mode,
        )
    return build_error_data(404, 'Not Found')


def make_debug_mode(frontik_app: FrontikApplication, tornado_request: HTTPServerRequest) -> DebugMode:
    debug_mode = DebugMode(tornado_request)

    if not debug_mode.need_auth:
        return debug_mode

    if hasattr(frontik_app, 'require_debug_access'):
        frontik_app.require_debug_access(debug_mode, tornado_request)
    else:
        debug_mode.require_debug_access(tornado_request)

    return debug_mode


def make_debug_auth_failed_response(auth_header: str) -> FrontikResponse:
    return FrontikResponse(status_code=http.client.UNAUTHORIZED, headers={'WWW-Authenticate': auth_header})


def make_not_accepted_response() -> FrontikResponse:
    return FrontikResponse(status_code=http.client.SERVICE_UNAVAILABLE)


def build_error_data(status_code: int = 500, message: Optional[str] = 'Internal Server Error') -> FrontikResponse:
    headers = {'Content-Type': media_types.TEXT_HTML}
    data = f'<html><title>{status_code}: {message}</title><body>{status_code}: {message}</body></html>'.encode()
    return FrontikResponse(status_code=status_code, headers=headers, body=data)


async def execute_tornado_page(
    frontik_app: FrontikApplication,
    tornado_request: httputil.HTTPServerRequest,
    scope: dict,
    debug_mode: DebugMode,
) -> FrontikResponse:
    route, page_cls, path_params = scope['route'], scope['page_cls'], scope['path_params']
    request_context.set_handler_name(route)
    handler: PageHandler = page_cls(frontik_app, tornado_request, route, debug_mode, path_params)
    status_code, _, headers, body = await handler.execute()
    return FrontikResponse(status_code=status_code, headers=headers, body=body)


def _on_connection_close(tornado_request, process_request_task):
    process_request_task.cancel()
    log_request(tornado_request, CLIENT_CLOSED_REQUEST)
