import socket

import pytest
from tornado.escape import to_unicode

from frontik.app import FrontikApplication
from frontik.dependencies import statsd_client
from frontik.options import options
from frontik.routing import router
from frontik.testing import FrontikTestBase


@router.get('/statsd')
async def get_page() -> None:
    statsd_client.count('count_metric', 10, tag1='tag1', tag2='tag2')
    statsd_client.gauge('gauge_metric', 100, tag='tag3')
    statsd_client.time('time_metric', 1000, tag='tag4')


class TestStatsdIntegration(FrontikTestBase):
    @pytest.fixture(scope='class')
    def statsd_socket(self) -> socket.socket:
        _statsd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _statsd_socket.settimeout(0.1)
        _statsd_socket.bind(('', 0))

        port = _statsd_socket.getsockname()[1]

        options.service_name = 'test_app'
        options.statsd_host = '127.0.0.1'
        options.statsd_port = port

        return _statsd_socket

    @pytest.fixture(scope='class')
    def frontik_app(self, statsd_socket) -> FrontikApplication:  # type: ignore
        return FrontikApplication(app_module_name=None)

    async def test_send_to_statsd(self, statsd_socket):
        await self.fetch('/statsd')

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

        assert 'count_metric.tag1_is_tag1.tag2_is_tag2.app_is_test_app:10|c' in metrics
        assert 'gauge_metric.tag_is_tag3.app_is_test_app:100|g' in metrics
        assert 'time_metric.tag_is_tag4.app_is_test_app:1000|ms' in metrics
