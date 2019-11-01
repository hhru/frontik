import asyncio
from consul import Check
from consul.aio import Consul
from frontik.integrations import Integration, integrations_logger
from frontik.options import options
from frontik.version import version
import socket
from asyncio import Future
from typing import Optional


class ConsulIntegration(Integration):
    def __init__(self):
        self.consul = None
        self.service_id = None
        self.service_name = None

    def initialize_app(self, app) -> Optional[Future]:
        if not options.consul_enabled:
            integrations_logger.info('Consul disabled, skipping')
            return None

        host = socket.gethostname()
        self.consul = Consul(host=options.consul_host, port=options.consul_port)
        self.service_name = options.app
        self.service_id = f'{self.service_name}-{options.datacenter}-{host}-{options.port}'

        http_check = Check.http(
            f'http://{host}:{options.port}/status',
            options.consul_http_check_interval_sec,
            timeout=options.consul_http_check_timeout_sec
        )
        # not supported by version 1.1.0
        meta = {'serviceVersion': version}
        return asyncio.ensure_future(self.consul.agent.service.register(
            self.service_name,
            service_id=self.service_id,
            address=host,
            port=options.port,
            check=http_check,
            tags=options.consul_tags
        ))

    def deinitialize_app(self, app) -> Optional[Future]:
        if options.consul_enabled:
            return asyncio.ensure_future(self.consul.agent.service.deregister(self.service_id))

    def initialize_handler(self, handler):
        handler.service_discovery = self.consul
