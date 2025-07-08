import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from http_client.balancing import Server, Upstream, UpstreamConfigs
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from frontik.app import FrontikApplication
from frontik.app_integrations import scylla
from frontik.app_integrations.scylla import StatsdMetricsReporter, _DecoratedCluster
from frontik.app_integrations.statsd import StatsDClientStub
from frontik.options import options
from frontik.testing import FrontikTestBase

SCYLLA_PORT = 9042


class TestScyllaIntegration(FrontikTestBase):
    @pytest.fixture(scope='session', autouse=False)
    async def scylla_container(self) -> AsyncIterator[DockerContainer]:
        container = DockerContainer('scylladb/scylla:5.1.6')
        container.with_exposed_ports(SCYLLA_PORT)
        # Start the container
        container.start()
        # Wait for Scylla to be ready (listening on CQL port)
        wait_for_logs(container, 'Starting listening for CQL clients')
        yield container
        container.stop()

    @pytest.fixture(scope='session', autouse=False)
    def statsd_client(self) -> StatsDClientStub:
        client = StatsDClientStub()
        return client

    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

    # Verify that we record only allowed metrics
    async def test_allowed_metrics(self, scylla_container: DockerContainer, statsd_client: StatsDClientStub) -> None:
        host = scylla_container.get_container_host_ip()
        port = scylla_container.get_exposed_port(SCYLLA_PORT)
        address = f'{host}:{port}'

        # verify that we send only allowed metrics
        def gauge(aspect: str, value: float, **kwargs: dict[str, Any]) -> None:
            assert aspect in options.scylla_metrics_allowed

        statsd_client.gauge = gauge  # type: ignore[method-assign]

        # create at least one session so we could send metrics
        cluster_name = 'cluster1'
        server = Server(address, host)
        upstream_configs = UpstreamConfigs({})
        upstream = Upstream(cluster_name, upstream_configs, [server])
        cluster: _DecoratedCluster = scylla.create_monitored_cluster(str(uuid.uuid4()), upstream, statsd_client)

        session = await cluster.create_session('system')
        assert len(cluster.get_sessions()) == 1

        # test
        reporter = StatsdMetricsReporter(statsd_client, cluster, cluster_name)
        reporter.report_metrics()

        # cleanup session
        await session.close()
        assert len(cluster.get_sessions()) == 0

    # Verify that metric is updated
    async def test_updated_metric(self, scylla_container: DockerContainer, statsd_client: StatsDClientStub) -> None:
        host = scylla_container.get_container_host_ip()
        port = scylla_container.get_exposed_port(SCYLLA_PORT)
        address = f'{host}:{port}'
        metric_name = 'requests_max'

        # create at least one session so we could send metrics
        cluster_name = 'cluster1'
        server = Server(address, host)
        upstream_configs = UpstreamConfigs({})
        upstream = Upstream(cluster_name, upstream_configs, [server])
        cluster: _DecoratedCluster = scylla.create_monitored_cluster(str(uuid.uuid4()), upstream, statsd_client)

        session = await cluster.create_session('system')
        assert len(cluster.get_sessions()) == 1

        # test

        def gauge1(aspect: str, value: float, **kwargs: Any) -> None:  # noqa: ANN401
            # verify that we recorded metric value
            assert aspect == metric_name
            assert value >= 1.0

        statsd_client.gauge = gauge1  # type: ignore[method-assign]

        observed_metrics: tuple[str, ...] = (metric_name,)
        options.scylla_metrics_allowed = observed_metrics  # we are interested only in one metric
        await session.query('SELECT * FROM system.peers')  # type: ignore[misc] # make first request to count in metrics
        reporter = StatsdMetricsReporter(statsd_client, cluster, cluster_name)
        reporter.report_metrics()

        # verify that we updated metric value
        def gauge2(aspect: str, value: float, **kwargs: Any) -> None:  # noqa: ANN401
            assert aspect == metric_name
            assert value >= 2.0

        statsd_client.gauge = gauge2  # type: ignore[method-assign]

        await session.query('SELECT * FROM system.peers')  # type: ignore[misc] # make second request to count in metrics
        reporter.report_metrics()

        # cleanup session
        await session.close()
        assert len(cluster.get_sessions()) == 0

    # Verify that tags are set for metrics
    async def test_tagged_metric(self, scylla_container: DockerContainer, statsd_client: StatsDClientStub) -> None:
        host = scylla_container.get_container_host_ip()
        port = scylla_container.get_exposed_port(SCYLLA_PORT)
        address = f'{host}:{port}'

        # verify that we add tags to all metrics
        def gauge(aspect: str, value: float, **kwargs: Any) -> None:  # noqa: ANN401
            assert kwargs['cluster'] is not None
            assert kwargs['client_id'] is not None

        statsd_client.gauge = gauge  # type: ignore[method-assign]

        # create at least one session so we could send metrics
        cluster_name = 'cluster1'
        server = Server(address, host)
        upstream_configs = UpstreamConfigs({})
        upstream = Upstream(cluster_name, upstream_configs, [server])
        cluster: _DecoratedCluster = scylla.create_monitored_cluster(str(uuid.uuid4()), upstream, statsd_client)

        session = await cluster.create_session('system')
        assert len(cluster.get_sessions()) == 1

        # test
        reporter = StatsdMetricsReporter(statsd_client, cluster, cluster_name)
        reporter.report_metrics()

        # cleanup session
        await session.close()
        assert len(cluster.get_sessions()) == 0

    # Verify that report interval is configurable
    async def test_report_interval(self, scylla_container: DockerContainer, statsd_client: StatsDClientStub) -> None:
        host = scylla_container.get_container_host_ip()
        port = scylla_container.get_exposed_port(SCYLLA_PORT)
        address = f'{host}:{port}'

        # Invoke metrics at least once in a second
        options.scylla_metrics_report_interval = 1000

        self.invocation_count = 0

        def gauge(aspect: str, value: float, **kwargs: Any) -> None:  # noqa: ANN401
            self.invocation_count += 1

        statsd_client.gauge = gauge  # type: ignore[method-assign]

        # create at least one session so we could send metrics
        cluster_name = 'cluster1'
        server = Server(address, host)
        upstream_configs = UpstreamConfigs({})
        upstream = Upstream(cluster_name, upstream_configs, [server])
        cluster: _DecoratedCluster = scylla.create_monitored_cluster(str(uuid.uuid4()), upstream, statsd_client)

        session = await cluster.create_session('system')
        assert len(cluster.get_sessions()) == 1

        await asyncio.sleep(1)
        # ensure we reported metrics at least once
        assert self.invocation_count >= 1

        # cleanup session
        await session.close()
        assert len(cluster.get_sessions()) == 0

    # Verify that sessions are not lost
    async def test_unique_sessions(self, scylla_container: DockerContainer, statsd_client: StatsDClientStub) -> None:
        host = scylla_container.get_container_host_ip()
        port = scylla_container.get_exposed_port(SCYLLA_PORT)
        address = f'{host}:{port}'

        # create at least one session so we could send metrics
        cluster_name = 'cluster1'
        server = Server(address, host)
        upstream_configs = UpstreamConfigs({})
        upstream = Upstream(cluster_name, upstream_configs, [server])
        cluster: _DecoratedCluster = scylla.create_monitored_cluster(str(uuid.uuid4()), upstream, statsd_client)

        session1 = await cluster.create_session('system')
        assert len(cluster.get_sessions()) == 1

        session2 = await cluster.create_session('system')
        assert len(cluster.get_sessions()) == 2

        # cleanup session
        await session1.close()
        await session2.close()
        assert len(cluster.get_sessions()) == 0
