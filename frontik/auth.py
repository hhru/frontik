# coding=utf-8


def passed_basic_auth(handler, login, passwd):
    auth_header = handler.request.headers.get('Authorization')

    if auth_header:
        method, auth_b64 = auth_header.split(' ')
        given_login, _, given_passwd = auth_b64.decode('base64').partition(':')
        return login == given_login and passwd == given_passwd
    return False
