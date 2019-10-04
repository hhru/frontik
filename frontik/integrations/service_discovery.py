from typing import TYPE_CHECKING
import asyncio
from consul import Check
from consul.aio import Consul
from frontik.integrations import Integration
from frontik.options import options
import socket

if TYPE_CHECKING:
    from asyncio import Future
    from typing import Optional


class ConsulIntegration(Integration):
    def __init__(self):
        self.consul = None
        self.service_id = None
        self.service_name = None

    def initialize_app(self, app) -> Optional[Future]:
        if options.consul_port:
            host = socket.gethostname()
            self.consul = Consul(port=options.consul_port)
            self.service_name = options.app
            self.service_id = f'{self.service_name}-{options.datacenter}-{host}'

            http_check = Check.http(
                f'http://localhost:{options.port}/status',
                options.consul_http_check_interval_sec,
                timeout=options.consul_http_check_timeout_sec
            )

            return asyncio.ensure_future(self.consul.agent.service.register(
                self.service_name,
                service_id=self.service_id,
                address=host,
                port=options.port,
                check=http_check,
                tags=options.consul_tags,
            ))

    def deinitialize_app(self, app) -> Optional[Future]:
        return asyncio.ensure_future(self.consul.agent.service.deregister(self.service_id))

    def initialize_handler(self, handler):
        handler.service_discovery = self.consul
