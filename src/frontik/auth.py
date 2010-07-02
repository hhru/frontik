import tornado.options

class AuthError(Exception):
    pass

def _real_finish_require_auth(handler):
    handler.set_header('WWW-Authenticate', 'Basic realm="Secure Area"')
    handler.set_status(401)
    handler.finish("")

def basic(handler):
    auth_header = handler.request.headers.get('Authorization')

    if auth_header:
        method, auth_b64 = auth_header.split(' ')
        login, passwd = auth_b64.decode('base64').split(':')

        if login != tornado.options.options.debug_login or passwd != tornado.options.options.debug_password:
            _real_finish_require_auth(handler)
            raise AuthError()
    else:
        _real_finish_require_auth(handler)
        raise AuthError()
