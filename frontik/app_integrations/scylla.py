from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import acsylla
from acsylla.base import Cluster
from http_client.balancing import Upstream

from frontik.app_integrations import Integration
from frontik.options import options

if TYPE_CHECKING:
    from asyncio import Future

    from frontik.app import FrontikApplication


class ScyllaIntegration(Integration):
    def __init__(self):
        self.scylla_clusters = {}

    def initialize_app(self, app: FrontikApplication) -> Optional[Future]:
        def get_scylla_cluster(cluster_name: str) -> Optional[Cluster]:
            return self.scylla_clusters.get(cluster_name)

        app.get_scylla_cluster = get_scylla_cluster  # type: ignore

        if options.scylla_clusters:
            upstreams = app.service_discovery.get_upstreams_copy()

            for cluster_name in options.scylla_clusters:
                upstream: Upstream = upstreams.get('scylla-' + cluster_name)
                scylla_servers = [server.address.split(':')[0] for server in upstream.servers if server is not None]
                scylla_port = int(upstream.servers[0].address.split(':')[1])

                self.scylla_clusters[cluster_name] = acsylla.create_cluster(
                    scylla_servers,
                    port=scylla_port,
                )

        return None
