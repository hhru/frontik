import tornado.web

class AuthError(Exception):
    pass

def _require_auth(handler):
    handler.set_header('WWW-Authenticate', 'Basic realm="Secure Area"')
    handler.set_status(401)
    handler.finish("")
    
    raise AuthError()

def require_basic_auth(handler, login, passwd):
    auth_header = handler.request.headers.get('Authorization')

    if auth_header:
        method, auth_b64 = auth_header.split(' ')
        given_login, given_passwd = auth_b64.decode('base64').split(':')

        if login != given_login or passwd != given_passwd:
            handler.async_callback(_require_auth)(handler)
    else:
        handler.async_callback(_require_auth)(handler)
