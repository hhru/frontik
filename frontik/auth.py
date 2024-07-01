from __future__ import annotations

import base64
import http.client
from typing import TYPE_CHECKING, Optional

from tornado.escape import to_unicode
from tornado.web import Finish

from frontik.options import options

if TYPE_CHECKING:
    from tornado import httputil

    from frontik.handler import PageHandler

DEBUG_AUTH_HEADER_NAME = 'Frontik-Debug-Auth'


class DebugUnauthorizedError(Finish):
    pass


def passed_basic_auth(tornado_request: httputil.HTTPServerRequest, login: Optional[str], passwd: Optional[str]) -> bool:
    auth_header = tornado_request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Basic '):
        method, auth_b64 = auth_header.split(' ')
        try:
            decoded_value = to_unicode(base64.b64decode(auth_b64))
        except ValueError:
            return False
        given_login, _, given_passwd = decoded_value.partition(':')
        return login == given_login and passwd == given_passwd
    return False


def check_debug_auth(
    tornado_request: httputil.HTTPServerRequest, login: Optional[str], password: Optional[str]
) -> Optional[str]:
    debug_auth_header = tornado_request.headers.get(DEBUG_AUTH_HEADER_NAME)
    if debug_auth_header is not None:
        debug_access = debug_auth_header == f'{login}:{password}'
        if not debug_access:
            return f'{DEBUG_AUTH_HEADER_NAME}-Header realm="Secure Area"'
    else:
        debug_access = passed_basic_auth(tornado_request, login, password)
        if not debug_access:
            return 'Basic realm="Secure Area"'
    return None


def check_debug_auth_or_finish(
    handler: PageHandler, login: Optional[str] = None, password: Optional[str] = None
) -> None:
    if options.debug:
        return
    login = login or options.debug_login
    password = password or options.debug_password
    fail_header = check_debug_auth(handler.request, login, password)
    if fail_header:
        handler.set_header('WWW-Authenticate', fail_header)
        handler.set_status(http.client.UNAUTHORIZED)
        handler.finish()
