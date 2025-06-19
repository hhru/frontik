import http.client
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

import aiohttp
from fastapi import Request, Response
from http_client import RequestBuilder, extra_client_params
from http_client.request_response import (
    DEADLINE_TIMEOUT_MS_HEADER,
    INSUFFICIENT_TIMEOUT,
    OUTER_TIMEOUT_MS_HEADER,
    SERVER_TIMEOUT,
    USER_AGENT_HEADER,
    FailFastError,
)
from starlette.datastructures import Headers
from starlette.types import Scope

from frontik.auth import DEBUG_AUTH_HEADER_NAME
from frontik.debug import DEBUG_HEADER_NAME, DebugMode
from frontik.http_status import NON_CRITICAL_BAD_GATEWAY
from frontik.options import options
from frontik.request_integrations import request_context
from frontik.timeout_tracking import get_timeout_checker
from frontik.util import make_url
from frontik.util.fastapi import make_plain_response

log = logging.getLogger('handler')


def modify_http_client_request(
    server_request_headers: Headers,
    start_time: float,
    debug_mode: DebugMode,
    balanced_request: RequestBuilder,
) -> None:
    balanced_request.headers['x-request-id'] = request_context.get_request_id()
    balanced_request_timeout_ms = balanced_request.request_timeout * 1000
    balanced_request.headers[OUTER_TIMEOUT_MS_HEADER] = f'{balanced_request_timeout_ms:.0f}'

    if not options.http_client_decrease_timeout_by_deadline or DEADLINE_TIMEOUT_MS_HEADER not in server_request_headers:
        balanced_request.headers[DEADLINE_TIMEOUT_MS_HEADER] = f'{balanced_request_timeout_ms:.0f}'
    else:
        spent_time_ms = (time.time() - start_time) * 1000
        deadline_timeout_ms = min(
            int(server_request_headers[DEADLINE_TIMEOUT_MS_HEADER]) - spent_time_ms, balanced_request_timeout_ms
        )
        if deadline_timeout_ms <= 0:
            msg = 'negative http timeout is not allowed'
            raise RuntimeError(msg)

        balanced_request.headers[DEADLINE_TIMEOUT_MS_HEADER] = f'{deadline_timeout_ms:.0f}'
        balanced_request.request_timeout = deadline_timeout_ms / 1000
        balanced_request.timeout = aiohttp.ClientTimeout(
            total=balanced_request.request_timeout, connect=balanced_request.connect_timeout
        )

    outer_timeout = server_request_headers.get(OUTER_TIMEOUT_MS_HEADER.lower())
    if outer_timeout:
        timeout_checker = get_timeout_checker(
            server_request_headers.get(USER_AGENT_HEADER.lower()),
            float(outer_timeout),
            start_time,
        )
        timeout_checker.check(balanced_request)

    if debug_mode.pass_debug:
        balanced_request.headers[DEBUG_HEADER_NAME] = 'true'

        # debug_timestamp is added to avoid caching of debug responses
        balanced_request.path = make_url(balanced_request.path, debug_timestamp=int(time.time()))

        for header_name in ('Authorization', DEBUG_AUTH_HEADER_NAME):
            authorization = server_request_headers.get(header_name.lower())
            if authorization is not None:
                balanced_request.headers[header_name] = authorization


@contextmanager
def set_extra_client_params(scope: Scope) -> Iterator:
    headers = Headers(scope=scope)
    start_time = scope['start_time']
    debug_mode = scope['debug_mode']
    http_client_hook = scope.get('_http_client_hook')

    def hook(balanced_request):
        if (local_hook := http_client_hook) is not None:
            local_hook(balanced_request)

        modify_http_client_request(headers, start_time, debug_mode, balanced_request)

    debug_enabled = scope['debug_mode'].enabled

    token = extra_client_params.set((hook, debug_enabled))
    try:
        yield
    finally:
        extra_client_params.reset(token)


async def fail_fast_error_handler(server_request: Request, exc: FailFastError) -> Response:
    log.warning(exc)

    deadline_timeout = server_request.headers.get(DEADLINE_TIMEOUT_MS_HEADER)
    outer_timeout = server_request.headers.get(OUTER_TIMEOUT_MS_HEADER)
    server_has_insufficient_timeout = (
        deadline_timeout is not None and outer_timeout is not None and int(deadline_timeout) < int(outer_timeout)
    )

    if exc.failed_result.status_code == INSUFFICIENT_TIMEOUT:
        status_code = INSUFFICIENT_TIMEOUT if server_has_insufficient_timeout else SERVER_TIMEOUT
    elif exc.failed_result.status_code == SERVER_TIMEOUT:
        status_code = http.client.GATEWAY_TIMEOUT
    elif exc.failed_result.status_code in {
        NON_CRITICAL_BAD_GATEWAY,
        http.client.NOT_FOUND,
        http.client.FORBIDDEN,
        http.client.UNAUTHORIZED,
    }:
        status_code = exc.failed_result.status_code
    elif http.client.BAD_REQUEST <= exc.failed_result.status_code < http.client.INTERNAL_SERVER_ERROR:
        status_code = http.client.INTERNAL_SERVER_ERROR
    elif exc.failed_result.status_code >= http.client.INTERNAL_SERVER_ERROR:
        status_code = http.client.BAD_GATEWAY
    elif exc.failed_result.data_parsing_failed or exc.failed_result.exc is not None:
        status_code = http.client.INTERNAL_SERVER_ERROR
    else:
        status_code = exc.failed_result.status_code

    return make_plain_response(status_code)
