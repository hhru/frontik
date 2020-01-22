import logging
import socket

from consul import Check
from consul.aio import Consul

from frontik.options import options
from frontik.version import version

log = logging.getLogger('service_discovery')
_hostname = socket.gethostname()


class ServiceDiscovery:

    def __init__(self, opts):
        self.consul = Consul(host=opts.consul_host, port=opts.consul_port)
        self.service_name = opts.app
        self.service_id = self._make_service_id(opts)

    def _make_service_id(self, opts) -> str:
        return f'{self.service_name}-{opts.datacenter}-{_hostname}-{opts.port}'

    async def register_service(self):
        if not options.consul_enabled:
            log.info('Consul disabled, skipping')
            return None

        http_check = Check.http(
            f'http://{options.consul_check_host}:{options.port}/status',
            f'{options.consul_http_check_interval_sec}s',
            timeout=f'{options.consul_http_check_timeout_sec}s'
        )
        # not supported by version 1.1.0
        meta = {'serviceVersion': version}
        await self.consul.agent.service.register(
            self.service_name,
            service_id=self.service_id,
            address=_hostname,
            port=options.port,
            check=http_check,
            tags=options.consul_tags,
        )

    async def deregister_service(self):
        if not options.consul_enabled:
            log.info('Consul disabled, skipping')
            return None
        return self.consul.agent.service.deregister(self.service_id)
