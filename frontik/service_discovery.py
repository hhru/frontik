import logging
import multiprocessing
import socket

from consul import Check, Consul
from consul.aio import Consul as AsyncConsul
from consul.base import Weight, KVCache, ConsistencyMode, HealthCache
from http_client import UpstreamStore, consul_parser, Upstream
from tornado.options import options

from frontik.version import version

DEFAULT_WEIGHT = 100
AUTO_RESOLVE_ADDRESS_VALUE = 'resolve'

log = logging.getLogger('service_discovery')


def _get_service_address(options):
    if options.consul_service_address:
        if AUTO_RESOLVE_ADDRESS_VALUE == options.consul_service_address.lower():
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        return options.consul_service_address


def get_async_service_discovery(opts, *, event_loop=None):
    if not opts.consul_enabled:
        log.info('Consul disabled, skipping')
        return _AsyncStub()
    else:
        return _AsyncServiceDiscovery(opts, event_loop)


def get_sync_service_discovery(opts):
    if not opts.consul_enabled:
        log.info('Consul disabled, skipping')
        return _SyncStub()
    else:
        return _SyncServiceDiscovery(opts)


def _make_service_id(options, *, service_name, hostname):
    return f'{service_name}-{hostname}-{options.port}'


def _create_http_check(options, address):
    check_host = options.consul_check_host
    if not check_host:
        check_host = address if address else '127.0.0.1'
    http_check = Check.http(
        f'http://{check_host}:{options.port}/status',
        f'{options.consul_http_check_interval_sec}s',
        deregister=f'{options.consul_deregister_critical_timeout}',
        timeout=f'{options.consul_http_check_timeout_sec}s'
    )
    return http_check


# not supported by consul client version 1.1.0
def _create_meta():
    return {'serviceVersion': version}


def _get_weight_or_default(value):
    return int(value['Value']) if value is not None else DEFAULT_WEIGHT


def _get_hostname_or_raise(node_name: str):
    if not node_name:
        raise RuntimeError('options node_name must be defined')
    return node_name


class _AsyncServiceDiscovery:
    def __init__(self, options, event_loop=None):
        self.options = options
        self.consul = AsyncConsul(host=options.consul_host, port=options.consul_port, loop=event_loop)
        self.service_name = options.app
        self.hostname = _get_hostname_or_raise(options.node_name)
        self.service_id = _make_service_id(options, service_name=self.service_name, hostname=self.hostname)
        self.consul_weight_watch_seconds = f'{options.consul_weight_watch_seconds}s'
        self.consul_weight_total_timeout_sec = options.consul_weight_total_timeout_sec
        self.consul_weight_consistency_mode = ConsistencyMode(options.consul_weight_consistency_mode.lower())
        self.consul_cache_initial_warmup_timeout_sec = options.consul_cache_initial_warmup_timeout_sec

    async def register_service(self):
        address = _get_service_address(self.options)
        http_check = _create_http_check(self.options, address)
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
                    'address': address,
                    'port': self.options.port,
                    'check': http_check,
                    'tags': self.options.consul_tags,
                    'weights': Weight.weights(weight, 0)
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


class _SyncServiceDiscovery:
    def __init__(self, options):
        self.options = options
        self.consul = Consul(host=options.consul_host, port=options.consul_port)
        self.service_name = options.app
        self.hostname = _get_hostname_or_raise(options.node_name)
        self.service_id = _make_service_id(options, service_name=self.service_name, hostname=self.hostname)
        self.address = _get_service_address(options)
        self.http_check = _create_http_check(options, self.address)
        self.consul_weight_watch_seconds = f'{options.consul_weight_watch_seconds}s'
        self.consul_weight_total_timeout_sec = options.consul_weight_total_timeout_sec
        self.consul_weight_consistency_mode = ConsistencyMode(options.consul_weight_consistency_mode.lower())
        self.consul_cache_initial_warmup_timeout_sec = options.consul_cache_initial_warmup_timeout_sec
        self.consul_cache_backoff_delay_seconds = options.consul_cache_backoff_delay_seconds
        self.kvCache = KVCache(
            self.consul.kv,
            path=f'host/{self.hostname}/weight',
            watch_seconds=self.consul_weight_watch_seconds,
            backoff_delay_seconds=self.consul_cache_backoff_delay_seconds,
            total_timeout=self.consul_weight_total_timeout_sec,
            cache_initial_warmup_timeout=self.consul_cache_initial_warmup_timeout_sec,
            consistency_mode=self.consul_weight_consistency_mode,
            recurse=False
        )
        self.kvCache.add_listener(self._update_register, False)

    def _update_register(self, key, new_value):
        weight = _get_weight_or_default(new_value)
        self._sync_register(weight)

    def register_service(self):
        weight = _get_weight_or_default(self.kvCache.get_value())
        self._sync_register(weight)
        self.kvCache.start()

    def _sync_register(self, weight):
        register_params = {
            'service_id': self.service_id,
            'address': self.address,
            'port': self.options.port,
            'check': self.http_check,
            'tags': self.options.consul_tags,
            'weights': Weight.weights(weight, 0)
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


class UpstreamStoreSharedMemory(UpstreamStore):
    """
    Implementation for processing upstream via shared memory
    """

    def __init__(self, lock, upstreams):
        self.lock = lock
        self.upstreams = upstreams

    def get_upstream(self, host):
        with self.lock:
            shared_upstream = self.upstreams.get(host, None)

        return shared_upstream


class UpstreamCaches:
    def __init__(self):
        self._upstreams_config = {}
        self._upstreams_servers = {}
        self._upstream_list = options.upstreams
        self._datacenter_list = options.datacenters
        self._current_dc = options.datacenter
        self._allow_cross_dc_requests = options.http_client_allow_cross_datacenter_requests
        self._shared_objects_manager = multiprocessing.Manager()

        self.upstreams = self._shared_objects_manager.dict()
        self.lock = multiprocessing.Lock()

    def initial_upstreams_caches(self):
        service_discovery = get_sync_service_discovery(options)
        upstream_cache = KVCache(
            service_discovery.consul.kv,
            path='upstream/',
            watch_seconds=service_discovery.consul_weight_watch_seconds,
            backoff_delay_seconds=service_discovery.consul_cache_backoff_delay_seconds,
            total_timeout=service_discovery.consul_weight_total_timeout_sec,
            cache_initial_warmup_timeout=service_discovery.consul_cache_initial_warmup_timeout_sec,
            consistency_mode=service_discovery.consul_weight_consistency_mode,
            recurse=True
        )
        upstream_cache.add_listener(self._update_upstreams_config, True)
        upstream_cache.start()
        for upstream in self._upstream_list:
            if self._allow_cross_dc_requests:
                for dc in self._datacenter_list:
                    health_cache = HealthCache(
                        service=upstream,
                        health_client=service_discovery.consul.health,
                        passing=True,
                        watch_seconds=service_discovery.consul_weight_watch_seconds,
                        backoff_delay_seconds=service_discovery.consul_cache_backoff_delay_seconds,
                        dc=dc
                    )
                    health_cache.add_listener(self._update_upstreams_service, True)
                    health_cache.start()
            else:
                health_cache = HealthCache(
                    service=upstream,
                    health_client=service_discovery.consul.health,
                    passing=True,
                    watch_seconds=service_discovery.consul_weight_watch_seconds,
                    backoff_delay_seconds=service_discovery.consul_cache_backoff_delay_seconds,
                    dc=self._current_dc
                )
                health_cache.add_listener(self._update_upstreams_service, True)
                health_cache.start()
        if options.fail_start_on_empty_upstream:
            self._check_empty_upstreams_on_startup()

    def _check_empty_upstreams_on_startup(self):
        with self.lock:
            empty_upstreams = [k for k, v in self.upstreams.items() if not v.servers]
        if empty_upstreams:
            raise RuntimeError(
                f'failed startup application, because for next upstreams got empty servers: {empty_upstreams}'
            )

    def _update_upstreams_service(self, key, values):
        if values is not None:
            dc, servers = consul_parser.parse_consul_health_servers_data(values)
            log.info(f'update servers for upstream {key}: [{",".join(str(s) for s in servers)}]')
            self._upstreams_servers[f'{key}-{dc}'] = servers
            self._update_upstreams(key)

    def _update_upstreams_config(self, key, values):
        if values is not None:
            for value in values:
                if value['Value'] is not None:
                    key = value['Key'].split('/')[1]
                    if key in self._upstream_list:
                        config = consul_parser.parse_consul_upstream_config(value)
                        log.info(f'parsed upstream config for {key}:{config}')
                        self._upstreams_config[key] = config
                        self._update_upstreams(key)

    def _update_upstreams(self, key):
        servers_from_all_dc = self._combine_servers(key)
        log.info(f'current servers for upstream {key}: [{",".join(str(s) for s in servers_from_all_dc)}]')
        with self.lock:
            self.upstreams[key] = Upstream(key, self._upstreams_config.get(key, {}), servers_from_all_dc)

    def _combine_servers(self, key):
        servers_from_all_dc = []
        for dc in self._datacenter_list:
            servers = self._upstreams_servers.get(f'{key}-{dc}')
            if servers:
                servers_from_all_dc += servers
        return servers_from_all_dc

    def _stop_shared_objects_manager(self):
        self._shared_objects_manager.shutdown()
