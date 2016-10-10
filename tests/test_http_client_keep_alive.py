# coding=utf-8

import socket
import unittest
from contextlib import closing

from .instances import find_free_port, frontik_test_app


class HTTPClientKeepAliveTestCase(unittest.TestCase):
    """ Tests use frontik_client to send http request to frontik_keep_alive_app.
        Frontik_keep_alive_app proxies the request to backend.
        Backend is just a simple server socket.
        We write http response to accepted socket and check whether it is closed or not.
    """

    def setUp(self):
        self.backend = Backend()
        self.client = Client(frontik_test_app.port)

    def tearDown(self):
        self.client.close()
        self.backend.close()

    def test_http_client_reuses_connection_to_backend(self):
        self.client.send_request(self.backend.port)

        with self.backend.accept() as backend_socket:
            handle_request_to_backend(backend_socket, '204', 'No content')
            response = self.client.get_response()

            self.assertEqual('204', response.split('\r\n')[-1])

            self.client.send_request(self.backend.port)
            handle_request_to_backend(backend_socket, '204', 'No content')
            response = self.client.get_response()

            self.assertEqual('204', response.split('\r\n')[-1])

    def test_http_client_closes_connection_if_read_timeout(self):
        self.client.send_request(self.backend.port)

        with self.backend.accept() as backend_socket:
            backend_socket.recv(1024)
            response = self.client.get_response()

            self.assertEqual('599', response.split('\r\n')[-1])

            backend_socket.setblocking(0)
            self.assertEqual(b'', backend_socket.recv(1024), 'backend socket is not closed')

    def test_http_client_closes_connection_if_read_timeout_after_partial_response(self):
        self.client.send_request(self.backend.port)

        with self.backend.accept() as backend_socket:
            backend_socket.recv(1024)
            backend_socket.send(b'HTTP/1.1')
            response = self.client.get_response()

            self.assertEqual('599', response.split('\r\n')[-1])

            backend_socket.setblocking(0)
            self.assertEqual(b'', backend_socket.recv(1024), 'backend socket is not closed')


class Client(object):
    def __init__(self, port):
        self.port = port
        self.socket = socket.socket()
        self.socket.connect(('127.0.0.1', port))

    def send_request(self, backend_port, request_id=None):
        self.socket.send(b'GET /http_client/proxy_code?port=' + str(backend_port).encode() + b' HTTP/1.1\r\n')
        self.socket.send(b'Host: 127.0.0.1:' + str(self.port).encode() + b'\r\n')
        if request_id:
            self.socket.send(b'X-Request-Id: ' + request_id.encode() + b'\r\n')
        self.socket.send(b'\r\n')

    def get_response(self):
        return self.socket.recv(1024).decode()

    def close(self):
        self.socket.close()


class Backend(object):
    def __init__(self):
        self.port = find_free_port()
        self.socket = socket.socket()
        self.socket.bind(('127.0.0.1', self.port))
        self.socket.listen(1)

    def accept(self):
        socket, _ = self.socket.accept()
        return closing(socket)

    def close(self):
        self.socket.close()


def handle_request_to_backend(backend_socket, code, reason, headers=None):
    backend_socket.recv(1024)
    backend_socket.send(b'HTTP/1.1 ' + code.encode() + b' ' + reason.encode() + b'\r\n')
    if headers is not None:
        for header in headers:
            backend_socket.send(header.encode() + b'\r\n')
    backend_socket.send(b'\r\n')
