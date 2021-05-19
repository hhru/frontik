import socket
import unittest

from tornado.escape import to_unicode

from .instances import FrontikTestInstance


class TestStatsdIntegration(unittest.TestCase):
    def test_send_metrics_to_statsd(self):
        statsd_socket = self._get_udp_socket()
        port = statsd_socket.getsockname()[1]
        test_app = FrontikTestInstance(
            './frontik-test --app=tests.projects.test_app --config=tests/projects/frontik_debug.cfg '
            f'--statsd_host=127.0.0.1 --consul_enabled=False --statsd_port={port}'
        )

        test_app.get_page('timing_logger')
        test_app.stop()

        metrics = [l for l in self._read_all_metrics_from_socket(statsd_socket) if l.startswith('metric_name.')]
        self.assertEqual(len(metrics), 1)
        line = metrics[0]
        self.assertTrue('param1_is_1' in line)
        self.assertTrue('param2_is_param2' in line)

    def _get_udp_socket(self):
        statsd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        statsd_socket.settimeout(0.1)
        statsd_socket.bind(('', 0))
        return statsd_socket

    def _read_all_metrics_from_socket(self, statsd_socket):
        metrics = []
        try:
            chunk = statsd_socket.recv(1024 * 24)
            while chunk:
                metrics.append(to_unicode(chunk))
                chunk = statsd_socket.recv(1024 * 24)
        except socket.timeout:
            pass
        finally:
            statsd_socket.close()
        metrics = '\n'.join(metrics).split('\n')
        return metrics
