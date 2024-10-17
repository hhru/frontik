import socket

import pytest
from tornado.escape import to_unicode

from frontik.app import FrontikApplication
from frontik.app_integrations.statsd import StatsDClientT
from frontik.options import options
from frontik.routing import router
from frontik.testing import FrontikTestBase


@router.get("/statsd")
async def get_page(statsd_client: StatsDClientT):
    statsd_client.count("count_metric", 10, tag1="tag1", tag2="tag2")
    statsd_client.gauge("gauge_metric", 100, tag="tag3")
    statsd_client.time("time_metric", 1000, tag="tag4")


class TestStatsdIntegration(FrontikTestBase):
    @pytest.fixture(scope="class")
    def frontik_app(self) -> FrontikApplication:
        statsd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        statsd_socket.settimeout(0.1)
        statsd_socket.bind(("", 0))

        port = statsd_socket.getsockname()[1]

        options.service_name = "test_app"
        options.statsd_host = "127.0.0.1"
        options.statsd_port = port

        app = FrontikApplication()
        app.statsd_socket = statsd_socket

        return app

    async def test_send_to_statsd(self):
        await self.fetch("/statsd")

        metrics = []
        try:
            chunk = self.app.statsd_socket.recv(1024 * 24)
            while chunk:
                metrics.append(to_unicode(chunk))
                chunk = self.app.statsd_socket.recv(1024 * 24)
        except socket.timeout:
            pass
        finally:
            self.app.statsd_socket.close()

        metrics = "\n".join(metrics).split("\n")

        assert "count_metric.tag1_is_tag1.tag2_is_tag2.app_is_test_app:10|c" in metrics
        assert "gauge_metric.tag_is_tag3.app_is_test_app:100|g" in metrics
        assert "time_metric.tag_is_tag4.app_is_test_app:1000|ms" in metrics
