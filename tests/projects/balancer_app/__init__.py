from http_client.balancing import Server

from frontik.app import FrontikApplication


def get_server(handler, type):
    return Server(f'127.0.0.1:{handler.get_argument(type)}', dc='Test')


def get_server_with_port(port):
    return Server(f'127.0.0.1:{port}', dc='Test')


def get_non_listening_server():
    return Server('http://10.0.0.0:12345')


class TestApplication(FrontikApplication):
    pass
