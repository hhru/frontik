import tornado.web

def passed_basic_auth(handler, login, passwd):
    auth_header = handler.request.headers.get('Authorization')

    if auth_header:
        method, auth_b64 = auth_header.split(' ')
        given_login, given_passwd = auth_b64.decode('base64').split(':')

        if login == given_login or passwd == given_passwd:
            return True

    return False

