# coding=utf-8
import httplib

DEBUG_AUTH_HEADER_NAME = 'Frontik-Debug-Auth'


def passed_basic_auth(handler, login, passwd):
    auth_header = handler.request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Basic '):
        method, auth_b64 = auth_header.split(' ')
        try:
            decoded_value = auth_b64.decode('base64')
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
            return httplib.UNAUTHORIZED, {'WWW-Authenticate': '{}-Header realm="Secure Area"'.format(header_name)}
    else:
        debug_access = passed_basic_auth(handler, login, password)
        if not debug_access:
            return httplib.UNAUTHORIZED, {'WWW-Authenticate': 'Basic realm="Secure Area"'}
    return None
