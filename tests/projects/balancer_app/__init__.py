from fastapi import Request
from http_client.balancing import Server

from frontik.app import FrontikApplication


def get_server(request: Request, type: str) -> Server:
    return Server(f'127.0.0.1:{request.query_params.get(type)}', 'dest_host', dc='Test')


def get_server_with_port(port: int) -> Server:
    return Server(f'127.0.0.1:{port}', 'dest_host', dc='Test')


def get_non_listening_server() -> Server:
    return Server('http://10.0.0.0:12345')


class TestApplication(FrontikApplication):
    pass
