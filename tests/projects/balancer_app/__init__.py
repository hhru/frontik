from http_client import Server

from frontik.app import FrontikApplication


def get_server(handler, type):
    return Server('127.0.0.1:' + handler.get_argument(type))


def get_non_listening_server():
    return Server('http://10.0.0.0:12345')


class TestApplication(FrontikApplication):
    pass
