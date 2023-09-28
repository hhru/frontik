from __future__ import annotations

from typing import TYPE_CHECKING

from http_client.balancing import Server

from frontik.app import FrontikApplication

if TYPE_CHECKING:
    from frontik.handler import PageHandler


def get_server(handler: PageHandler, type: str) -> Server:
    return Server(f'127.0.0.1:{handler.get_argument(type)}', dc='Test')


def get_server_with_port(port: int) -> Server:
    return Server(f'127.0.0.1:{port}', dc='Test')


def get_non_listening_server() -> Server:
    return Server('http://10.0.0.0:12345')


class TestApplication(FrontikApplication):
    pass
