import base64
from typing import Mapping, MutableMapping, Optional, Union

from tornado import httputil
from tornado.escape import to_unicode
from tornado.web import Finish

DEBUG_AUTH_HEADER_NAME = 'Frontik-Debug-Auth'


class DebugUnauthorizedError(Finish):
    pass


def passed_basic_auth(auth_header: str, login: Optional[str], passwd: Optional[str]) -> bool:
    if auth_header and auth_header.startswith('Basic '):
        method, auth_b64 = auth_header.split(' ')
        try:
            decoded_value = to_unicode(base64.b64decode(auth_b64))
        except ValueError:
            return False
        given_login, _, given_passwd = decoded_value.partition(':')
        return login == given_login and passwd == given_passwd
    return False


def check_debug_auth_by_headers(
    headers: Union[Mapping, MutableMapping], login: Optional[str], password: Optional[str]
) -> Optional[str]:
    debug_auth_header = headers.get(DEBUG_AUTH_HEADER_NAME)
    if debug_auth_header is not None:
        debug_access = debug_auth_header == f'{login}:{password}'
        if not debug_access:
            return f'{DEBUG_AUTH_HEADER_NAME}-Header realm="Secure Area"'
    else:
        auth_header = headers.get('Authorization')
        debug_access = passed_basic_auth(auth_header, login, password)
        if not debug_access:
            return 'Basic realm="Secure Area"'
    return None


def check_debug_auth(
    tornado_request: httputil.HTTPServerRequest, login: Optional[str], password: Optional[str]
) -> Optional[str]:
    return check_debug_auth_by_headers(tornado_request.headers, login, password)
