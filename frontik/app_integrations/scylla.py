from __future__ import annotations

import asyncio
import logging
from asyncio import Future
from dataclasses import fields
from typing import TYPE_CHECKING, Callable, Optional

from acsylla import (
    create_cluster,
)

from frontik.app_integrations import Integration
from frontik.options import options
from frontik.util import run_async_task
from frontik.util.abc import Delegator

if TYPE_CHECKING:
    from acsylla.base import (
        Cluster,
        Session,
        SessionMetrics,
    )
    from http_client.balancing import Upstream
    from pystatsd import StatsDClientABC

    from frontik.app import FrontikApplication

LOGGER = logging.getLogger('scylla')


class ScyllaIntegration(Integration):
    def __init__(self) -> None:
        self.scylla_clusters: dict[str, Cluster] = {}

    def initialize_app(self, app: FrontikApplication) -> Optional[Future]:
        def get_scylla_cluster(cluster_name: str) -> Optional[Cluster]:
            return self.scylla_clusters.get(cluster_name)

        app.get_scylla_cluster = get_scylla_cluster  # type: ignore[method-assign]

        if options.scylla_clusters:
            assert options.datacenter is not None
            upstreams = app.service_discovery.get_upstreams_copy()

            for cluster_name in options.scylla_clusters:
                upstream_name = 'scylla-' + cluster_name
                upstream: Upstream | None = upstreams.get(upstream_name)
                if upstream is None:
                    LOGGER.error('Upstream "%s" does not exist', upstream_name)
                    continue
                self.scylla_clusters[cluster_name] = create_monitored_cluster(cluster_name, upstream, app.statsd_client)  # type: ignore[assignment]

        return None


def create_monitored_cluster(
    cluster_name: str, upstream: Upstream, statsd_client: StatsDClientABC
) -> _DecoratedCluster:
    scylla_servers = [server for server in upstream.servers if server is not None]
    scylla_servers_address = [server.address.split(':')[0] for server in scylla_servers]
    upstream_server = scylla_servers[0]
    if upstream_server is None:
        msg = f'Servers are not specified for %{cluster_name}'
        raise RuntimeError(msg)
    scylla_port = int(upstream_server.address.split(':')[1])

    native_cluster = create_cluster(
        scylla_servers_address,
        port=scylla_port,
        local_port_range_min=None,
        local_port_range_max=None,
        # load_balance_dc_aware should be explicitly specified, because client knows every node in cluster
        # and takes random one every time even with consistency_level=LOCAL_QUORUM
        load_balance_dc_aware=None if options.scylla_cross_dc_enabled else options.datacenter,
        log_level=options.scylla_log_level,
        retry_policy_logging=options.scylla_retry_policy_logging,
    )
    cluster = _DecoratedCluster(native_cluster)

    if options.scylla_metrics_send_stats and statsd_client is not None:
        reporter = StatsdMetricsReporter(statsd_client, cluster, cluster_name)
        run_async_task(reporter.report())

    return cluster


class StatsdMetricsReporter:
    def __init__(
        self,
        statsd_client: StatsDClientABC,
        cluster: _DecoratedCluster,
        cluster_name: str,
    ) -> None:
        self.statsd_client = statsd_client
        self.cluster = cluster
        self.cluster_name = cluster_name
        self.allowed_metrics: tuple[str, ...] = options.scylla_metrics_allowed
        self.metrics_report_interval: int = options.scylla_metrics_report_interval

    def report_metrics(self) -> None:
        for session in self.cluster.get_sessions():
            try:
                metrics: SessionMetrics = session.metrics()
            except Exception:
                msg = f'Unable to report any metrics for {session.get_client_id()}'
                LOGGER.exception(msg)
                continue

            for field in fields(metrics):
                if field.name not in self.allowed_metrics:
                    continue
                try:
                    # Comply with tag from a java scylla client `cluster`
                    self.statsd_client.gauge(
                        field.name,
                        float(getattr(metrics, field.name)),
                        cluster=self.cluster_name,
                        client_id=session.get_client_id(),
                    )
                except Exception:
                    msg = f'Unable to report metric {field.name} for {session.get_client_id()}'
                    LOGGER.exception(msg)
                    continue

    async def report(self) -> None:
        while True:
            await asyncio.sleep(self.metrics_report_interval / 1000)
            self.report_metrics()


class _DecoratedSession(Delegator):
    def __init__(self, native_session: Session) -> None:
        super().__init__(native_session)
        self.cleanup_callback: Callable[[_DecoratedSession], None] = lambda _: None

    def set_cleanup(self, cleanup_callback: Callable[[_DecoratedSession], None]) -> None:
        self.cleanup_callback = cleanup_callback

    # overridden
    async def close(self) -> None:
        self.cleanup_callback(self)
        await self.delegator.close()


class _DecoratedCluster(Delegator):
    def __init__(self, native_cluster: Cluster) -> None:
        super().__init__(native_cluster)
        self.__sessions: set[_DecoratedSession] = set()

    def get_sessions(self) -> set[_DecoratedSession]:
        return self.__sessions

    # overridden
    async def create_session(self, keyspace: str | None = None) -> Session:
        session: Session = await self.delegator.create_session(keyspace)
        decorator = _DecoratedSession(session)
        decorator.set_cleanup(self.__sessions.discard)
        self.__sessions.add(decorator)
        return decorator  # type: ignore[return-value]
