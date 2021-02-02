#!/usr/bin/env python3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from frontik.options import options
from frontik.server import main


class MockConsulRequestHandler(BaseHTTPRequestHandler):

    def do_PUT(self):
        self.send_response(200)
        self.end_headers()
        return


def run_consul_mock_server():
    """
    you need to run consul agent to be able to run frontik application
    if you don't want to use consul add consul_enabled=False in config
    """

    server = HTTPServer(('localhost', 0), MockConsulRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    return server


if __name__ == '__main__':
    server = run_consul_mock_server()
    # consul_port need to defined in config file,
    # but for easily startup example we in-line free local machine port in options
    options.consul_port = server.server_port
    main('./frontik.cfg')
