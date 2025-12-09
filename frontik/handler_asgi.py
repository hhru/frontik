from __future__ import annotations

import asyncio
import http.client
import logging
from contextlib import ExitStack
from functools import partial
from typing import TYPE_CHECKING

from tornado.httputil import ResponseStartLine
from tornado.iostream import StreamClosedError

from frontik.debug import DebugMode, DebugTransform
from frontik.frontik_response import FrontikResponse
from frontik.http_status import CLIENT_CLOSED_REQUEST
from frontik.loggers import CUSTOM_JSON_EXTRA, JSON_REQUESTS_LOGGER
from frontik.request_integrations import get_integrations, request_context
from frontik.request_integrations.integrations_dto import IntegrationDto
from frontik.routing import find_route
from frontik.tornado_request import EOF
from frontik.util.fastapi import make_plain_response

if TYPE_CHECKING:
    from fastapi import Request, Response

    from frontik.app import FrontikApplication
    from frontik.tornado_request import FrontikTornadoServerRequest

CHARSET = 'utf-8'
log = logging.getLogger('handler')


async def serve_tornado_request(
    frontik_app: FrontikApplication,
    tornado_request: FrontikTornadoServerRequest,
) -> None:
    with ExitStack() as stack:
        integrations: dict[str, IntegrationDto] = {
            ctx_name: stack.enter_context(ctx(frontik_app, tornado_request)) for ctx_name, ctx in get_integrations()
        }
        log.info('requested url: %s', tornado_request.uri)

        process_request_task = asyncio.create_task(process_request(frontik_app, tornado_request, integrations))
        assert tornado_request.connection is not None
        tornado_request.connection.set_close_callback(  # type: ignore
            partial(
                _on_connection_close,
                tornado_request,
                process_request_task,
                integrations,
            )
        )

        response: FrontikResponse = await process_request_task

        assert tornado_request.connection is not None
        tornado_request.connection.set_close_callback(None)  # type: ignore

        if getattr(tornado_request, 'canceled', False):
            return

        if not response.headers_written:
            start_line = ResponseStartLine('', response.status_code, response.reason)
            await write_start_line(tornado_request, start_line, response, response.body)

        log_request(tornado_request, response.status_code)
        for integration in integrations.values():
            integration.set_response(response)
        tornado_request.connection.finish()


async def process_request(
    frontik_app: FrontikApplication,
    tornado_request: FrontikTornadoServerRequest,
    integrations: dict[str, IntegrationDto],
) -> FrontikResponse:
    if integrations.get('request_limiter', IntegrationDto()).get_value() is False:
        return FrontikResponse(status_code=http.client.SERVICE_UNAVAILABLE)

    debug_mode = make_debug_mode(frontik_app, tornado_request)
    if debug_mode.auth_failed:
        return FrontikResponse(status_code=http.client.UNAUTHORIZED, headers=debug_mode.failed_auth_headers)

    assert tornado_request.method is not None

    if frontik_app.route_manager:
        frontik_app.route_manager.import_route(tornado_request.path, tornado_request.method)
    scope = find_route(tornado_request.path, tornado_request.method, None)
    tornado_request._path_format = scope['route'].path_format  # type: ignore

    response = await execute_asgi_page(frontik_app, tornado_request, scope, debug_mode, integrations)

    if debug_mode.debug_response and not response.headers_written:
        debug_transform = DebugTransform(frontik_app, debug_mode)
        response = debug_transform.transform_chunk(tornado_request, response)

    return response


async def execute_asgi_page(
    frontik_app: FrontikApplication,
    tornado_request: FrontikTornadoServerRequest,
    scope: dict,
    debug_mode: DebugMode,
    integrations: dict[str, IntegrationDto],
) -> FrontikResponse:
    request_context.set_handler_name(scope['route'])
    tornado_request.handler_name = request_context.get_handler_name()

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
        'debug_mode': debug_mode,
        'frontik_app': frontik_app,
        'start_time': tornado_request._start_time,  # noqa:SLF001
        'request_id': tornado_request.request_id,
    })

    async def receive():
        chunk = await tornado_request.body_chunks.get()

        if tornado_request.canceled:
            return {
                'type': 'http.disconnect',
            }

        if tornado_request.finished and chunk == EOF:
            return {
                'body': b'',
                'type': 'http.request',
                'more_body': False,
            }

        return {
            'body': chunk,
            'type': 'http.request',
            'more_body': not tornado_request.finished or chunk != EOF,
        }

    async def send(message):
        assert tornado_request.connection is not None

        if message['type'] == 'http.response.start':
            response.status_code = int(message['status'])
            for h in message['headers']:
                if len(h) == 2:
                    response.headers.add(h[0].decode(CHARSET), h[1].decode(CHARSET))
        elif message['type'] == 'http.response.body':
            chunk = message['body']
            if debug_mode.debug_response:
                response.body += chunk
            elif not response.headers_written:
                for integration in integrations.values():
                    integration.set_response(response)

                start_line = ResponseStartLine('', response.status_code, response.reason)
                await write_start_line(tornado_request, start_line, response, chunk)
                response.headers_written = True
            else:
                if chunk == b'' and message['more_body'] is False:
                    tornado_request.response_done = True
                    return
                await tornado_request.connection.write(chunk)
        else:
            raise RuntimeError(f'Unsupported response type "{message["type"]}" for asgi app')

    try:
        await frontik_app(scope, receive, send)
    except Exception:
        pass
    finally:
        scope.clear()

    return response


def make_debug_mode(frontik_app: FrontikApplication, tornado_request: FrontikTornadoServerRequest) -> DebugMode:
    debug_mode = DebugMode(tornado_request)

    if not debug_mode.need_auth:
        return debug_mode

    if hasattr(frontik_app, 'require_debug_access'):
        frontik_app.require_debug_access(debug_mode, tornado_request.headers, tornado_request.cookies)
    else:
        debug_mode.require_debug_access(tornado_request.headers)

    return debug_mode


def _on_connection_close(tornado_request, process_request_task, integrations):
    if getattr(tornado_request, 'response_done', False):
        return

    request_id = integrations.get('request_context', IntegrationDto()).get_value()
    log.info('client has canceled request rid: %s', request_id)

    response = FrontikResponse(CLIENT_CLOSED_REQUEST, request_id=request_id)
    log_request(tornado_request, CLIENT_CLOSED_REQUEST)
    tornado_request.canceled = True

    for integration in integrations.values():
        integration.set_response(response)

    process_request_task.cancel()  # serve_tornado_request will be interrupted with CanceledError


def log_request(tornado_request: FrontikTornadoServerRequest, status_code: int) -> None:
    # request_context can't be used in case when client has closed connection
    request_time = int(1000.0 * tornado_request.request_time())
    extra = {
        'ip': tornado_request.remote_ip,
        'rid': tornado_request.request_id,
        'status': status_code,
        'time': request_time,
        'method': tornado_request.method,
        'uri': tornado_request.uri,
    }

    if tornado_request.handler_name:
        extra['controller'] = tornado_request.handler_name

    JSON_REQUESTS_LOGGER.info('', extra={CUSTOM_JSON_EXTRA: extra})


async def write_start_line(
    tornado_request: FrontikTornadoServerRequest,
    start_line: ResponseStartLine,
    response: FrontikResponse,
    chunk: bytes,
) -> None:
    try:
        assert tornado_request.connection is not None
        if tornado_request.method == 'HEAD':
            chunk = b''
        await tornado_request.connection.write_headers(start_line, response.headers, chunk)
    except StreamClosedError:
        response.status_code = CLIENT_CLOSED_REQUEST
        log.info(
            'client closed the connection while writing to the socket, rid: %s',
            request_context.get_request_id(),
        )


async def default_exception_handler(server_request: Request, exc: Exception) -> Response:
    log.error('failed to execute page', exc_info=exc)
    return make_plain_response(status_code=500)
