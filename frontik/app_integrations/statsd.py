from __future__ import annotations

import socket
from typing import TYPE_CHECKING, Optional

from pystatsd import StatsDClient, StatsDClientABC, StatsDClientStub

from frontik.app_integrations import Integration, integrations_logger

if TYPE_CHECKING:
    from asyncio import Future

    from frontik.app import FrontikApplication
    from frontik.options import Options


class StatsdIntegration(Integration):
    def __init__(self):
        self.statsd_client = None

    def initialize_app(self, app: FrontikApplication) -> Optional[Future]:
        self.statsd_client = app.statsd_client
        self.statsd_client.init()
        return None


def create_statsd_client(options: Options, app: FrontikApplication) -> StatsDClientABC:
    if options.statsd_host is None or options.statsd_port is None:
        statsd_client = StatsDClientStub()
        integrations_logger.info('statsd integration is disabled: statsd_host / statsd_port options are not configured')
    else:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setblocking(False)  # noqa: FBT003
        udp_socket.connect((options.statsd_host, options.statsd_port))

        assert options.statsd_max_udp_size is not None

        statsd_client = StatsDClient(
            options.statsd_host,
            options.statsd_port,
            default_periodic_send_interval_sec=options.statsd_default_periodic_send_interval_sec,
            max_udp_size_bytes=options.statsd_max_udp_size,
            udp_socket=udp_socket,
            default_tags={'app': app.app_name},
        )
    return statsd_client
