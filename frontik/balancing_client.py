import time
from collections.abc import Iterator
from contextlib import contextmanager

from http_client import RequestBuilder, extra_client_params
from http_client.request_response import USER_AGENT_HEADER
from starlette.datastructures import Headers
from starlette.types import Scope

from frontik.auth import DEBUG_AUTH_HEADER_NAME
from frontik.debug import DEBUG_HEADER_NAME, DebugMode
from frontik.request_integrations import request_context
from frontik.timeout_tracking import get_timeout_checker
from frontik.util import make_url

OUTER_TIMEOUT_MS_HEADER = 'X-Outer-Timeout-Ms'


def modify_http_client_request(
    headers: Headers,
    start_time: float,
    debug_mode: DebugMode,
    balanced_request: RequestBuilder,
) -> None:
    balanced_request.headers['x-request-id'] = request_context.get_request_id()
    balanced_request.headers[OUTER_TIMEOUT_MS_HEADER] = f'{balanced_request.request_timeout * 1000:.0f}'

    outer_timeout = headers.get(OUTER_TIMEOUT_MS_HEADER.lower())
    if outer_timeout:
        timeout_checker = get_timeout_checker(
            headers.get(USER_AGENT_HEADER.lower()),
            float(outer_timeout),
            start_time,
        )
        timeout_checker.check(balanced_request)

    if debug_mode.pass_debug:
        balanced_request.headers[DEBUG_HEADER_NAME] = 'true'

        # debug_timestamp is added to avoid caching of debug responses
        balanced_request.path = make_url(balanced_request.path, debug_timestamp=int(time.time()))

        for header_name in ('Authorization', DEBUG_AUTH_HEADER_NAME):
            authorization = headers.get(header_name.lower())
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
