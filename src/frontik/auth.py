import tornado.options

class AuthError(Exception):
    pass

def basic(handler):
    auth_header = handler.request.headers.get('Authorization')

    if auth_header:
        method, auth_b64 = auth_header.split(' ')
        login, passwd = auth_b64.decode('base64').split(':')

        if login != tornado.options.options.debug_login or passwd != tornado.options.options.debug_password:
            handler._real_finish_require_auth()
            raise AuthError()
    else:
        handler._real_finish_require_auth()
        raise AuthError()
