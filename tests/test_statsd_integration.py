import socket

from tornado.escape import to_unicode

from tests import FRONTIK_ROOT
from tests.instances import FrontikTestInstance

FRONTIK_RUN = f'{FRONTIK_ROOT}/frontik-test'
TEST_PROJECTS = f'{FRONTIK_ROOT}/tests/projects'


class TestStatsdIntegration:
    def test_send_to_statsd(self):
        statsd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        statsd_socket.settimeout(0.1)
        statsd_socket.bind(('', 0))

        port = statsd_socket.getsockname()[1]

        test_app = FrontikTestInstance(
            f'{FRONTIK_RUN} --app=tests.projects.test_app --config={TEST_PROJECTS}/frontik_debug.cfg '
            f'--statsd_host=127.0.0.1 --consul_enabled=False --statsd_port={port}',
        )

        test_app.get_page('statsd')
        test_app.stop()

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

        assert 'count_metric.tag1_is_tag1.tag2_is_tag2.app_is_tests-projects-test_app:10|c' in metrics
        assert 'gauge_metric.tag_is_tag3.app_is_tests-projects-test_app:100|g' in metrics
        assert 'time_metric.tag_is_tag4.app_is_tests-projects-test_app:1000|ms' in metrics
