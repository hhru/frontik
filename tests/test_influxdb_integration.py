import threading
import socket
import unittest

from tornado.escape import to_unicode

from .instances import FrontikTestInstance


class TestInfluxdbIntegration(unittest.TestCase):
    def test_send_to_influxdb(self):
        influxdb_socket = socket.socket()
        influxdb_socket.bind(('127.0.0.1', 0))
        influxdb_socket.listen(1)

        port = influxdb_socket.getsockname()[1]

        test_app = FrontikTestInstance(
            './frontik-test --app=tests.projects.test_app --config=tests/projects/frontik_debug.cfg --datacenter=test '
            '--influxdb_host=127.0.0.1 --influxdb_port={} '
            '--influxdb_metrics_db=metrics --influxdb_metrics_rp=hour'.format(port)
        )

        metrics = []

        def influx_mock():
            client_socket, _ = influxdb_socket.accept()
            client_socket.settimeout(0.1)

            while True:
                try:
                    chunk = client_socket.recv(1024 * 24)
                    if not chunk:
                        break

                    metrics.append(to_unicode(chunk))
                except socket.timeout:
                    break

            client_socket.close()

        threading.Thread(target=influx_mock).start()
        test_app.get_page('influxdb')

        test_app_port = test_app.port
        test_app.stop()
        influxdb_socket.close()

        self.assertEqual('POST /write?db=metrics&rp=hour HTTP/1.1', metrics[0].split('\r\n')[0])
        self.assertRegexpMatches(
            metrics[1],
            'request,app=tests.projects.test_app,current_dc=test,current_server=[^,]+,dc=None,final=true,'
            'server=127.0.0.1:{port},status=500,upstream=127.0.0.1:{port} response_time=[0-9]+'.format(
                port=test_app_port
            )
        )
