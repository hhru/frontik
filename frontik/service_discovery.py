import logging

from consul import Check, Consul
from consul.aio import Consul as AsyncConsul
from consul.base import Weight, KVCache

from frontik.version import version

DEFAULT_WEIGHT = 100

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
    return f'{service_name}-{hostname}-{options.port}'


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


def _get_weight_or_default(value):
    return int(value['Value']) if value is not None else DEFAULT_WEIGHT


class _AsyncServiceDiscovery:
    def __init__(self, options, hostname, event_loop=None):
        self.options = options
        self.consul = AsyncConsul(host=options.consul_host, port=options.consul_port, loop=event_loop)
        self.service_name = options.app
        self.hostname = hostname
        self.service_id = _make_service_id(options, service_name=self.service_name, hostname=self.hostname)
        self.consul_weight_watch_seconds = f'{options.consul_weight_watch_seconds}s'
        self.consul_weight_total_timeout_sec = options.consul_weight_total_timeout_sec
        self.consul_check_warning_divider = options.consul_check_warning_divider
        self.consul_weight_consistency_mode = options.consul_weight_consistency_mode.lower()

    async def register_service(self):
        http_check = _create_http_check(self.options)
        index = None
        old_weight = None
        while True:
            index, value = await self.consul.kv.get(
                f'host/{self.hostname}/weight',
                index=index,
                wait=self.consul_weight_watch_seconds,
                total_timeout=self.consul_weight_total_timeout_sec,
                consistency=self.consul_weight_consistency_mode,
            )
            weight = _get_weight_or_default(value)
            if old_weight != weight:
                old_weight = weight
                register_params = {
                    'service_id': self.service_id,
                    'address': self.hostname,
                    'port': self.options.port,
                    'check': http_check,
                    'tags': self.options.consul_tags,
                    'weights': Weight.weights(weight, int(weight / self.consul_check_warning_divider))
                }
                if await self.consul.agent.service.register(self.service_name, **register_params):
                    log.info('Successfully registered service %s', register_params)
                else:
                    raise Exception(f'Failed to register {self.service_id}')

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
        self.http_check = _create_http_check(options)
        self.consul_weight_watch_seconds = f'{options.consul_weight_watch_seconds}s'
        self.consul_weight_total_timeout_sec = options.consul_weight_total_timeout_sec
        self.consul_check_warning_divider = options.consul_check_warning_divider
        self.consul_weight_consistency_mode = options.consul_weight_consistency_mode.lower()
        self.kvCache = KVCache(
            self.consul.kv,
            path=f'host/{self.hostname}/weight',
            watch_seconds=self.consul_weight_watch_seconds,
            total_timeout=self.consul_weight_total_timeout_sec,
            consistency_mode=self.consul_weight_consistency_mode,
        )
        self.kvCache.add_listener(self._update_register, False)

    def _update_register(self, new_value):
        weight = _get_weight_or_default(new_value)
        self._sync_register(self.http_check, weight)

    def register_service(self):
        weight = _get_weight_or_default(self.kvCache.get_value())
        self._sync_register(self.http_check, weight)
        self.kvCache.start()

    def _sync_register(self, http_check, weight):
        register_params = {
            'service_id': self.service_id,
            'address': self.hostname,
            'port': self.options.port,
            'check': http_check,
            'tags': self.options.consul_tags,
            'weights': Weight.weights(weight, int(weight / self.consul_check_warning_divider))
        }
        if self.consul.agent.service.register(self.service_name, **register_params):
            log.info('Successfully registered service %s', register_params)
        else:
            raise Exception(f'Failed to register {register_params}')

    def deregister_service_and_close(self):
        self.kvCache.stop()
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
