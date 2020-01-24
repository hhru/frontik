import logging
import socket

from consul import Check, Consul
from consul.aio import Consul as AsyncConsul

from frontik.options import options
from frontik.version import version

log = logging.getLogger('service_discovery')
_hostname = socket.gethostname()


def _make_service_id(service_name, options):
    return f'{service_name}-{options.datacenter}-{_hostname}-{options.port}'


class ServiceDiscovery:

    def __init__(self, opts, event_loop=None):
        self.consul = AsyncConsul(host=opts.consul_host, port=opts.consul_port, loop=event_loop)
        self.service_name = opts.app
        self.service_id = _make_service_id(self.service_name, opts)

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
        log.info('Successfully registered service %s', self.service_id)

    async def deregister_service_and_close(self):
        if not options.consul_enabled:
            log.info('Consul disabled, skipping')
            return None
        if await self.consul.agent.service.deregister(self.service_id):
            log.info('Successfully deregistered service %s', self.service_id)
        else:
            log.info('Failed to deregister service %s normally', self.service_id)
        self.consul.close()


class SyncServiceDiscovery:
    def __init__(self, opts):
        self.consul = Consul(host=opts.consul_host, port=opts.consul_port)
        self.service_name = opts.app
        self.service_id = _make_service_id(self.service_name, opts)

    def register_service(self):
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
        if self.consul.agent.service.register(
            self.service_name,
            service_id=self.service_id,
            address=_hostname,
            port=options.port,
            check=http_check,
            tags=options.consul_tags,
        ):
            log.info('Successfully registered service %s', self.service_id)
        else:
            raise Exception(f'Failed to register {self.service_id}')

    def deregister_service_and_close(self):
        if not options.consul_enabled:
            log.info('Consul disabled, skipping')
            return None
        if self.consul.agent.service.deregister(self.service_id):
            log.info('Successfully deregistered service %s', self.service_id)
        else:
            log.info('Failed to deregister service %s normally', self.service_id)
