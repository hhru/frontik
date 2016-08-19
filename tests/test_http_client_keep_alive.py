# coding=utf-8
import socket

import unittest
from contextlib import closing

from .instances import FrontikTestInstance, find_free_port


class HTTPClientKeepAliveTestCase(unittest.TestCase):
    """ Tests use frontik_client to send http request to frontik_keep_alive_app.
        Frontik_keep_alive_app proxies the request to backend.
        Backend is just a simple server socket.
        We write http response to accepted socket and check whether it is closed or not.
    """

    def setUp(self):

        self._backend = Backend()

        if not frontik_keep_alive_app.port:
            frontik_keep_alive_app.start()

        self._frontik_client = FrontikClient(frontik_keep_alive_app.port)

    def tearDown(self):
        self._frontik_client.close()
        self._backend.close()

    def test_http_client_reuses_connection_to_backend(self):

        self._frontik_client.send_request(self._backend.port)

        with self._backend.accept() as backend_socket:

            _handle_request_to_backend(backend_socket, '204', 'No content')
            response1 = self._frontik_client.get_response()
            self.assertEqual('204', response1.split('\r\n')[-1])

            self._frontik_client.send_request(self._backend.port)
            _handle_request_to_backend(backend_socket, '204', 'No content')

            response2 = self._frontik_client.get_response()
            self.assertEqual('204', response2.split('\r\n')[-1])

    def test_http_client_closes_connection_if_read_timeout(self):

        self._frontik_client.send_request(self._backend.port)

        with self._backend.accept() as backend_socket:
            backend_socket.recv(1024)

            response = self._frontik_client.get_response()
            self.assertEqual('599', response.split('\r\n')[-1])

            backend_socket.setblocking(0)
            self.assertEqual(b'', backend_socket.recv(1024), 'backend socket is not closed')

    def test_http_client_closes_connection_if_read_timeout_after_partial_response(self):

        self._frontik_client.send_request(self._backend.port)

        with self._backend.accept() as backend_socket:
            backend_socket.recv(1024)
            backend_socket.send(b'HTTP/1.1')

            response = self._frontik_client.get_response()
            self.assertEqual('599', response.split('\r\n')[-1])

            backend_socket.setblocking(0)
            self.assertEqual(b'', backend_socket.recv(1024), 'backend socket is not closed')


class HTTPClientCheckRequestIdTestCase(unittest.TestCase):

    def setUp(self):
        self._backend = Backend()

        if not frontik_keep_alive_app.port:
            frontik_keep_alive_app.start()

        self._frontik_client = FrontikClient(frontik_keep_alive_app.port)

    def tearDown(self):
        self._frontik_client.close()
        self._backend.close()

    def test_request_id_matches(self):

        self._frontik_client.send_request(self._backend.port, 'some_request_id')

        with self._backend.accept() as backend_socket:

            _handle_request_to_backend(backend_socket, '204', 'No content', ['X-Request-ID: some_request_id'])
            response = self._frontik_client.get_response()
            self.assertEqual('204', response.split('\r\n')[-1])

    def test_wrong_request_id(self):

        self._frontik_client.send_request(self._backend.port, 'some_request_id')

        with self._backend.accept() as backend_socket:

            _handle_request_to_backend(backend_socket, '204', 'No content', ['X-Request-ID: wrong_request_id'])
            response = self._frontik_client.get_response()
            self.assertEqual('599', response.split('\r\n')[-1])

    def test_wrong_request_id_cache_control_max_age(self):

        self._frontik_client.send_request(self._backend.port, 'some_request_id')

        with self._backend.accept() as backend_socket:

            backend_response_headers = ['X-Request-ID: wrong_request_id', 'Cache-Control: max-age=300']
            _handle_request_to_backend(backend_socket, '204', 'No content', backend_response_headers)
            response = self._frontik_client.get_response()
            self.assertEqual('204', response.split('\r\n')[-1])

    def test_wrong_request_id_cache_control_no_store(self):

        self._frontik_client.send_request(self._backend.port, 'some_request_id')

        with self._backend.accept() as backend_socket:

            backend_response_headers = ['X-Request-ID: wrong_request_id', 'Cache-Control: no-store']
            _handle_request_to_backend(backend_socket, '204', 'No content', backend_response_headers)
            response = self._frontik_client.get_response()
            self.assertEqual('599', response.split('\r\n')[-1])

    def test_wrong_request_id_expires_future(self):

        self._frontik_client.send_request(self._backend.port, 'some_request_id')

        with self._backend.accept() as backend_socket:

            backend_response_headers = ['X-Request-ID: wrong_request_id', 'Expires: Thu, 11 Aug 2027 08:49:37 GMT']
            _handle_request_to_backend(backend_socket, '204', 'No content', backend_response_headers)
            response = self._frontik_client.get_response()
            self.assertEqual('204', response.split('\r\n')[-1])

    def test_wrong_request_id_expires_past(self):

        self._frontik_client.send_request(self._backend.port, 'some_request_id')

        with self._backend.accept() as backend_socket:

            backend_response_headers = ['X-Request-ID: wrong_request_id', 'Expires: Thu, 11 Aug 1970 08:49:37 GMT']
            _handle_request_to_backend(backend_socket, '204', 'No content', backend_response_headers)
            response = self._frontik_client.get_response()
            self.assertEqual('599', response.split('\r\n')[-1])


class FrontikClient(object):
    def __init__(self, frontik_port):
        self._frontik_port = frontik_port
        self._socket = socket.socket()
        self._socket.connect(('127.0.0.1', frontik_port))

    def send_request(self, backend_port, request_id=None):
        self._socket.send(b'GET /proxy_code?port=' + str(backend_port).encode() + b' HTTP/1.1\r\n')
        self._socket.send(b'Host: 127.0.0.1:' + str(self._frontik_port).encode() + b'\r\n')
        if request_id:
            self._socket.send(b'X-Request-Id: ' + request_id.encode() + b'\r\n')
        self._socket.send(b'\r\n')

    def get_response(self):
        return self._socket.recv(1024).decode()

    def close(self):
        self._socket.close()


class Backend(object):
    def __init__(self):
        self._server_port = find_free_port()
        self._server_socket = socket.socket()
        self._server_socket.bind(('127.0.0.1', self._server_port))
        self._server_socket.listen(1)

    @property
    def port(self):
        return self._server_port

    def accept(self):
        socket, _ = self._server_socket.accept()
        return closing(socket)

    def close(self):
        self._server_socket.close()


def _handle_request_to_backend(backend_socket, code, reason, headers=None):
    backend_socket.recv(1024)
    backend_socket.send(b'HTTP/1.1 ' + code.encode() + b' ' + reason.encode() + b'\r\n')
    if headers is not None:
        for header in headers:
            backend_socket.send(header.encode() + b'\r\n')
    backend_socket.send(b'\r\n')


frontik_keep_alive_app = FrontikTestInstance('supervisor-keepaliveapp')
