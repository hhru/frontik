from http_client.balancing import Server

from frontik.app import FrontikApplication
from frontik.handler import PageHandler


def get_server(handler: PageHandler, type: str) -> Server:
    return Server(f'127.0.0.1:{handler.get_query_argument(type)}', 'dest_host', dc='Test')


def get_server_with_port(port: int) -> Server:
    return Server(f'127.0.0.1:{port}', 'dest_host', dc='Test')


def get_non_listening_server() -> Server:
    return Server('http://10.0.0.0:12345')


class TestApplication(FrontikApplication):
    pass
