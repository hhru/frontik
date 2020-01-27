import logging

from consul import Check, Consul
from consul.aio import Consul as AsyncConsul

from frontik.version import version

log = logging.getLogger('service_discovery')


def get_async_service_discovery(opts, *, hostname, event_loop=None):
    if not opts.consul_enabled:
        log.info('Consul disabled, skipping')
        return _AsyncStub()
    else:
        return _AsyncServiceDiscovery(opts, hostname, event_loop)


def get_sync_service_discovery(opts, *, hostname):
    if not opts.consul_enabled:
        log.info('Consul disabled, skipping')
        return _SyncStub()
    else:
        return _SyncServiceDiscovery(opts, hostname)


def _make_service_id(options, *, service_name, hostname):
    return f'{service_name}-{options.datacenter}-{hostname}-{options.port}'


def _create_http_check(options):
    http_check = Check.http(
        f'http://{options.consul_check_host}:{options.port}/status',
        f'{options.consul_http_check_interval_sec}s',
        timeout=f'{options.consul_http_check_timeout_sec}s'
    )
    return http_check


# not supported by consul client version 1.1.0
def _create_meta():
    return {'serviceVersion': version}


class _AsyncServiceDiscovery:
    def __init__(self, options, hostname, event_loop=None):
        self.options = options
        self.consul = AsyncConsul(host=options.consul_host, port=options.consul_port, loop=event_loop)
        self.service_name = options.app
        self.hostname = hostname
        self.service_id = _make_service_id(options, service_name=self.service_name, hostname=self.hostname)

    async def register_service(self):
        http_check = _create_http_check(self.options)
        await self.consul.agent.service.register(
            self.service_name,
            service_id=self.service_id,
            address=self.hostname,
            port=self.options.port,
            check=http_check,
            tags=self.options.consul_tags,
        )
        log.info('Successfully registered service %s', self.service_id)

    async def deregister_service_and_close(self):
        if await self.consul.agent.service.deregister(self.service_id):
            log.info('Successfully deregistered service %s', self.service_id)
        else:
            log.info('Failed to deregister service %s normally', self.service_id)
        self.consul.close()


class _SyncServiceDiscovery:
    def __init__(self, options, hostname):
        self.options = options
        self.consul = Consul(host=options.consul_host, port=options.consul_port)
        self.service_name = options.app
        self.hostname = hostname
        self.service_id = _make_service_id(options, service_name=self.service_name, hostname=self.hostname)

    def register_service(self):
        http_check = _create_http_check(self.options)
        if self.consul.agent.service.register(
            self.service_name,
            service_id=self.service_id,
            address=self.hostname,
            port=self.options.port,
            check=http_check,
            tags=self.options.consul_tags,
        ):
            log.info('Successfully registered service %s', self.service_id)
        else:
            raise Exception(f'Failed to register {self.service_id}')

    def deregister_service_and_close(self):
        if self.consul.agent.service.deregister(self.service_id):
            log.info('Successfully deregistered service %s', self.service_id)
        else:
            log.info('Failed to deregister service %s normally', self.service_id)


class _AsyncStub:
    async def register_service(self):
        pass

    async def deregister_service_and_close(self):
        pass


class _SyncStub:
    def register_service(self):
        pass

    def deregister_service_and_close(self):
        pass
