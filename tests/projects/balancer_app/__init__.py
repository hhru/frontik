from frontik.app import FrontikApplication
from frontik.http_client import Server


def get_server(handler, type):
    return Server('127.0.0.1:' + handler.get_argument(type))


def get_non_listening_server():
    return Server('http://10.0.0.0:12345')


class TestApplication(FrontikApplication):
    pass
