import tornado.web

def _require_auth(handler):
    handler.set_header('WWW-Authenticate', 'Basic realm="Secure Area"')
    handler.set_status(401)
    handler.finish("")
        
def require_basic_auth(real_login, real_passwd):
    def new_deco(fun):
        def new_fun(handler, *args, **kw):
            auth_header = handler.request.headers.get('Authorization')
            if auth_header:
                method, auth_b64 = auth_header.split(' ')
                login, passwd = auth_b64.decode('base64').split(':')
                if login == real_login and passwd == real_passwd:
                    return fun(handler, *args, **kw)
                else:
                    _require_auth(handler)
            else:
                _require_auth(handler)
        return new_fun
    return new_deco


