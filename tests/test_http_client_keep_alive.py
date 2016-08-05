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

        with closing(self._backend.accept()) as backend_socket:

            _handle_request_to_backend(backend_socket, '204', 'No content')
            response1 = self._frontik_client.get_response()
            self.assertEqual('204', response1.split('\r\n')[-1])

            self._frontik_client.send_request(self._backend.port)
            _handle_request_to_backend(backend_socket, '204', 'No content')

            response2 = self._frontik_client.get_response()
            self.assertEqual('204', response2.split('\r\n')[-1])

    def test_http_client_closes_connection_if_read_timeout(self):

        self._frontik_client.send_request(self._backend.port)

        with closing(self._backend.accept()) as backend_socket:
            backend_socket.recv(1024)

            response = self._frontik_client.get_response()
            self.assertEqual('599', response.split('\r\n')[-1])

            backend_socket.setblocking(0)
            self.assertEqual('', backend_socket.recv(1024), 'backend socket is not closed')

    def test_http_client_closes_connection_if_read_timeout_after_partial_response(self):

        self._frontik_client.send_request(self._backend.port)

        with closing(self._backend.accept()) as backend_socket:
            backend_socket.recv(1024)
            backend_socket.send('HTTP/1.1')

            response = self._frontik_client.get_response()
            self.assertEqual('599', response.split('\r\n')[-1])

            backend_socket.setblocking(0)
            self.assertEqual('', backend_socket.recv(1024), 'backend socket is not closed')


class FrontikClient(object):
    def __init__(self, frontik_port):
        self._frontik_port = frontik_port
        self._socket = socket.socket()
        self._socket.connect(('127.0.0.1', frontik_port))

    def send_request(self, backend_port):
        self._socket.send('GET /proxy_code?port=' + str(backend_port) + ' HTTP/1.1\r\n')
        self._socket.send('Host: 127.0.0.1:' + str(self._frontik_port) + '\r\n')
        self._socket.send('\r\n')

    def get_response(self):
        return self._socket.recv(1024)

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
        return socket

    def close(self):
        self._server_socket.close()


def _handle_request_to_backend(backend_socket, code, reason):
    backend_socket.recv(1024)
    backend_socket.send('HTTP/1.1 ' + code + ' ' + reason + '\r\n')
    backend_socket.send('\r\n')


frontik_keep_alive_app = FrontikTestInstance('supervisor-keepaliveapp')
