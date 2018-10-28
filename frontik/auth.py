# coding=utf-8

import base64

from tornado.escape import to_unicode
from tornado.web import Finish

from frontik import http_codes

DEBUG_AUTH_HEADER_NAME = 'Frontik-Debug-Auth'


class DebugUnauthorizedError(Finish):
    pass


def passed_basic_auth(handler, login, passwd):
    auth_header = handler.request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Basic '):
        method, auth_b64 = auth_header.split(' ')
        try:
            decoded_value = to_unicode(base64.b64decode(auth_b64))
        except ValueError:
            return False
        given_login, _, given_passwd = decoded_value.partition(':')
        return login == given_login and passwd == given_passwd
    return False


def check_debug_auth(handler, login, password):
    """
    :type handler: tornado.web.RequestHandler
    :return: None or tuple(http_code, headers)
    """
    header_name = DEBUG_AUTH_HEADER_NAME
    debug_auth_header = handler.request.headers.get(header_name)
    if debug_auth_header is not None:
        debug_access = (debug_auth_header == '{}:{}'.format(login, password))
        if not debug_access:
            handler.set_header('WWW-Authenticate', '{}-Header realm="Secure Area"'.format(header_name))
            handler.set_status(http_codes.UNAUTHORIZED)
            raise DebugUnauthorizedError()
    else:
        debug_access = passed_basic_auth(handler, login, password)
        if not debug_access:
            handler.set_header('WWW-Authenticate', 'Basic realm="Secure Area"')
            handler.set_status(http_codes.UNAUTHORIZED)
            raise DebugUnauthorizedError()
