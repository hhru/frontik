import socket
from contextlib import closing
from typing import Any, Optional

from tests import find_free_port
from tests.instances import frontik_test_app


class TestHTTPClientKeepAlive:
    """
    Tests use frontik_client to send http request to frontik_keep_alive_app.
    Frontik_keep_alive_app proxies the request to backend.
    Backend is just a simple server socket.
    We write http response to accepted socket and check whether it is closed or not.
    """

    def setup_method(self):
        self.backend = Backend()
        frontik_test_app.start()
        if frontik_test_app.port is None:
            raise Exception('app port can not be None')
        self.client = Client(frontik_test_app.port)

    def teardown_method(self):
        self.client.close()
        self.backend.close()

    def test_http_client_reuses_connection_to_backend(self):
        self.client.send_request(self.backend.port)

        with self.backend.accept() as backend_socket:
            handle_request_to_backend(backend_socket, '204', 'No content')
            response = self.client.get_response()

            assert response.split('\r\n')[-1] == '204'

            self.client.send_request(self.backend.port)
            handle_request_to_backend(backend_socket, '204', 'No content')
            response = self.client.get_response()

            assert response.split('\r\n')[-1] == '204'

    def test_http_client_closes_connection_if_read_timeout(self):
        self.client.send_request(self.backend.port)

        with self.backend.accept() as backend_socket:
            backend_socket.recv(1024)
            response = self.client.get_response()

            assert response.split('\r\n')[-1] == '577'

            backend_socket.setblocking(0)
            assert backend_socket.recv(1024) == b'', 'backend socket is not closed'

    def test_http_client_closes_connection_if_read_timeout_after_partial_response(self):
        self.client.send_request(self.backend.port)

        with self.backend.accept() as backend_socket:
            backend_socket.recv(1024)
            backend_socket.send(b'HTTP/1.1')
            response = self.client.get_response()

            assert response.split('\r\n')[-1] == '577'

            backend_socket.setblocking(0)
            assert backend_socket.recv(1024) == b'', 'backend socket is not closed'


class Client:
    def __init__(self, port: int) -> None:
        self.port = port
        self.socket = socket.socket()
        self.socket.connect(('127.0.0.1', port))
        self.socket.settimeout(5)

    def send_request(self, backend_port: int, request_id: Optional[str] = None) -> None:
        self.socket.send(b'GET /http_client/proxy_code?port=' + str(backend_port).encode() + b' HTTP/1.1\r\n')
        self.socket.send(b'Host: 127.0.0.1:' + str(self.port).encode() + b'\r\n')
        if request_id:
            self.socket.send(b'X-Request-Id: ' + request_id.encode() + b'\r\n')
        self.socket.send(b'\r\n')

    def get_response(self) -> Any:
        headers = self.socket.recv(1024)
        if headers.endswith(b'\r\n'):
            body = self.socket.recv(1024)
            return headers.decode() + body.decode()
        return headers.decode()

    def close(self) -> None:
        self.socket.close()


class Backend:
    def __init__(self) -> None:
        self.port = find_free_port()
        self.socket = socket.socket()
        self.socket.bind(('127.0.0.1', self.port))
        self.socket.listen(1)

    def accept(self) -> closing:
        socket, _ = self.socket.accept()
        return closing(socket)

    def close(self) -> None:
        self.socket.close()


def handle_request_to_backend(backend_socket: socket.socket, code: str, reason: str, headers: Any = None) -> None:
    backend_socket.recv(1024)
    backend_socket.send(b'HTTP/1.1 ' + code.encode() + b' ' + reason.encode() + b'\r\n')
    if headers is not None:
        for header in headers:
            backend_socket.send(header.encode() + b'\r\n')
    backend_socket.send(b'\r\n')
