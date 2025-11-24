import abc
import itertools
import logging
import pickle
import socket
from copy import deepcopy
from random import shuffle
from threading import Lock
from typing import Any, Callable, Optional

from consul.base import Check, ConsistencyMode, HealthCache, KVCache, Weight
from http_client import options as http_options
from http_client.balancing import Server, Upstream, UpstreamConfigs
from http_client.parsing import consul_parser
from pystatsd import StatsDClientABC

from frontik.consul_client import ClientEventCallback, SyncConsulClient
from frontik.options import Options, options
from frontik.version import version

DEFAULT_WEIGHT = 100
AUTO_RESOLVE_ADDRESS_VALUE = 'resolve'

CONSUL_REQUESTS_METRIC = 'consul-client.request'
CONSUL_REQUEST_SUCCESSFUL_RESULT = 'success'
CONSUL_REQUEST_FAILED_RESULT = 'failure'

log = logging.getLogger('service_discovery')


def _get_service_address(options: Options) -> Optional[str]:
    if options.consul_service_address:
        if options.consul_service_address.lower() == AUTO_RESOLVE_ADDRESS_VALUE:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        return options.consul_service_address

    return None


def _make_service_id(options: Options, *, service_name: Optional[str], hostname: str) -> str:
    return f'{service_name}-{hostname}-{options.port}'


def _create_http_check(options: Options, address: Optional[str]) -> dict:
    check_host = options.consul_check_host
    if not check_host:
        check_host = address or '127.0.0.1'
    http_check = Check.http(
        f'http://{check_host}:{options.port}/status',
        f'{options.consul_http_check_interval_sec}s',
        deregister=f'{options.consul_deregister_critical_timeout}',
        timeout=f'{options.consul_http_check_timeout_sec}s',
    )
    return http_check


# not supported by consul client version 1.1.0
def _create_meta():
    return {'serviceVersion': version}


def _get_weight_or_default(value: Optional[dict]) -> int:
    return int(value['Value']) if value is not None else DEFAULT_WEIGHT


def _get_hostname_or_raise(node_name: str) -> str:
    if not node_name:
        raise RuntimeError('options node_name must be defined')
    return node_name


class ServiceDiscovery(abc.ABC):
    @abc.abstractmethod
    def get_upstreams_copy(self) -> dict[str, Upstream]:
        pass

    @abc.abstractmethod
    def get_upstream(self, upstream_name: str, default: None = None) -> Upstream:
        pass

    @abc.abstractmethod
    def register_service(self) -> None:
        pass

    @abc.abstractmethod
    def deregister_service_and_close(self) -> None:
        pass

    @abc.abstractmethod
    def get_upstreams_with_lock(self) -> tuple[dict[str, Upstream], Optional[Lock]]:
        pass

    @abc.abstractmethod
    def set_update_shared_data_hook(self, update_shared_data_hook: Callable) -> None:
        pass

    @abc.abstractmethod
    def update_upstreams(self, upstreams: list[Upstream]) -> None:
        pass

    @abc.abstractmethod
    def send_updates(self, upstream: Optional[Upstream] = None) -> None:
        pass


class MasterServiceDiscovery(ServiceDiscovery):
    def __init__(self, statsd_client: StatsDClientABC, app_name: str) -> None:
        self._upstreams_config: dict[str, UpstreamConfigs] = {}
        self._upstreams_servers: dict[str, list[Server]] = {}

        self._upstreams: dict[str, Upstream] = {}
        self._upstreams_lock = Lock()
        self._send_to_all_workers: Optional[Callable] = None

        self.consul = SyncConsulClient(
            host=options.consul_host,
            port=options.consul_port,
            client_event_callback=ConsulMetricsTracker(statsd_client),
        )
        self.service_name = app_name
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
            recurse=False,
            caller=self.service_name,
        )
        self.kvCache.add_listener(self._update_register)

        upstream_cache = KVCache(
            self.consul.kv,
            path='upstream/',
            watch_seconds=self.consul_weight_watch_seconds,
            backoff_delay_seconds=self.consul_cache_backoff_delay_seconds,
            total_timeout=self.consul_weight_total_timeout_sec,
            cache_initial_warmup_timeout=self.consul_cache_initial_warmup_timeout_sec,
            consistency_mode=self.consul_weight_consistency_mode,
            recurse=True,
            caller=self.service_name,
        )
        upstream_cache.add_listener(self._update_upstreams_config, trigger_current=True)
        upstream_cache.start()

        cross_datacenter_upstreams = (
            options.cross_datacenter_upstreams.split(',') if options.cross_datacenter_upstreams else []
        )

        for upstream, dc in itertools.product(options.upstreams, http_options.datacenters):
            if (
                dc == http_options.datacenter
                or '*' in cross_datacenter_upstreams
                or upstream in cross_datacenter_upstreams
            ):
                self.__subscribe_to_service(upstream, dc)

        kafka_upstreams = ['kafka-' + kafka_name for kafka_name in options.kafka_clusters]
        scylla_upstreams = ['scylla-' + scylla_name for scylla_name in options.scylla_clusters]
        for upstream, dc in itertools.product(kafka_upstreams + scylla_upstreams, http_options.datacenters):
            self.__subscribe_to_service(upstream, dc)

        if options.fail_start_on_empty_upstream:
            self.__check_empty_upstreams_on_startup()

    def __subscribe_to_service(self, service_name: str, dc: str) -> None:
        health_cache = HealthCache(
            service=service_name,
            health_client=self.consul.health,
            passing=True,
            watch_seconds=self.consul_weight_watch_seconds,
            backoff_delay_seconds=self.consul_cache_backoff_delay_seconds,
            dc=dc,
            caller=self.service_name,
        )
        health_cache.add_listener(self._update_upstreams_service, trigger_current=True)
        health_cache.start()

    def set_update_shared_data_hook(self, update_shared_data_hook: Callable) -> None:
        self._send_to_all_workers = update_shared_data_hook

    def get_upstreams_with_lock(self) -> tuple[dict[str, Upstream], Lock]:
        return self._upstreams, self._upstreams_lock

    def get_upstreams_copy(self) -> dict[str, Upstream]:
        with self._upstreams_lock:
            return deepcopy(self._upstreams)

    def get_upstream(self, upstream_name: str, default: None = None) -> Upstream:
        with self._upstreams_lock:
            return self._upstreams.get(upstream_name, default)

    def _update_register(self, key, new_value):
        weight = _get_weight_or_default(new_value)
        self._sync_register(weight)

    def register_service(self) -> None:
        weight = _get_weight_or_default(self.kvCache.get_value())
        self._sync_register(weight)
        self.kvCache.start()

    def _sync_register(self, weight: int) -> None:
        register_params = {
            'service_id': self.service_id,
            'address': self.address,
            'port': options.port,
            'check': self.http_check,
            'tags': options.consul_tags,
            'weights': Weight.weights(weight, 0),
            'caller': self.service_name,
        }
        if self.consul.agent.service.register(self.service_name, **register_params):
            log.info('Successfully registered service %s', register_params)
        else:
            raise Exception(f'Failed to register {register_params}')

    def deregister_service_and_close(self) -> None:
        self.kvCache.stop()
        if self.consul.agent.service.deregister(self.service_id, self.service_name):
            log.info('Successfully deregistered service %s', self.service_id)
        else:
            log.info('Failed to deregister service %s normally', self.service_id)

    def __check_empty_upstreams_on_startup(self) -> None:
        skip_check_upstreams = options.skip_empty_upstream_check_for_upstreams
        empty_upstreams = [k for k, v in self._upstreams.items() if not v.servers and k not in skip_check_upstreams]
        if empty_upstreams:
            msg = f'failed startup application, because for next upstreams got empty servers: {empty_upstreams}'
            raise RuntimeError(msg)

    def _update_upstreams_service(self, key: str, values: list) -> None:
        if values is not None:
            dc, servers = consul_parser.parse_consul_health_servers_data(values)
            servers_str = ','.join(str(s) for s in servers)
            log.info('update servers for upstream %s, datacenter %s: [%s]', key, dc, servers_str)
            self._upstreams_servers[f'{key}-{dc}'] = servers
            self._update_upstreams(key)

    def _update_upstreams_config(self, key: str, values: Optional[list[dict[str, Any]]]) -> None:
        if values is not None:
            for value in values:
                if value['Value'] is not None:
                    key = value['Key'].split('/')[1]
                    if key in options.upstreams:
                        config = consul_parser.parse_consul_upstream_config(value)
                        log.info('parsed upstream config for %s:%s', key, config)
                        self._upstreams_config[key] = config
                        self._update_upstreams(key)

    def _update_upstreams(self, key: str) -> None:
        with self._upstreams_lock:
            upstream = self._create_upstream(key)
            servers = ','.join(str(s) for s in upstream.servers)
            log.info('current servers for upstream %s: [%s]', key, servers)

            current_upstream = self._upstreams.get(key)

            if current_upstream is None:
                self._upstreams[key] = upstream
            else:
                current_upstream.update(upstream)

        self.send_updates(upstream=upstream)

    def send_updates(self, upstream: Optional[Upstream] = None) -> None:
        if self._send_to_all_workers is None:
            return
        with self._upstreams_lock:
            upstreams = list(self._upstreams.values()) if upstream is None else [upstream]
            self._send_to_all_workers(pickle.dumps(upstreams))

    def _create_upstream(self, key: str) -> Upstream:
        servers = self._combine_servers(key)
        shuffle(servers)
        return Upstream(key, self._upstreams_config.get(key, UpstreamConfigs({})), servers)

    def _combine_servers(self, key: str) -> list[Server]:
        servers_from_all_dc = []
        for dc in http_options.datacenters:
            servers = self._upstreams_servers.get(f'{key}-{dc}')
            if servers:
                servers_from_all_dc += servers
        return servers_from_all_dc

    def update_upstreams(self, upstreams: list[Upstream]) -> None:
        raise RuntimeError('master should not serve upstream updates')


class WorkerServiceDiscovery(ServiceDiscovery):
    def __init__(self, upstreams: dict[str, Upstream]) -> None:
        self._upstreams = upstreams
        self._upstreams_lock = Lock()

    def update_upstreams(self, upstreams: list[Upstream]) -> None:
        for upstream in upstreams:
            self.__update_upstream(upstream)

    def __update_upstream(self, upstream: Upstream) -> None:
        current_upstream = self._upstreams.get(upstream.name)

        if current_upstream is None:
            shuffle(upstream.servers)
            self._upstreams[upstream.name] = upstream
            log.debug('add %s upstream: %s', upstream.name, str(upstream))
            return

        current_upstream.update(upstream)
        log.debug('update %s upstream: %s', upstream.name, str(upstream))

    def get_upstreams_copy(self) -> dict[str, Upstream]:
        return deepcopy(self._upstreams)

    def get_upstream(self, upstream_name: str, default: None = None) -> Upstream:
        return self._upstreams.get(upstream_name, default)

    def register_service(self) -> None:
        pass

    def deregister_service_and_close(self) -> None:
        pass

    def get_upstreams_with_lock(self) -> tuple[dict[str, Upstream], Optional[Lock]]:
        return self._upstreams, self._upstreams_lock

    def set_update_shared_data_hook(self, update_shared_data_hook: Callable) -> None:
        raise RuntimeError('worker should not use update hook')

    def send_updates(self, upstream: Optional[Upstream] = None) -> None:
        raise RuntimeError('worker should not use send updates')


class ConsulMetricsTracker(ClientEventCallback):
    def __init__(self, statsd_client: StatsDClientABC) -> None:
        self._statsd_client = statsd_client

    def on_http_request_success(self, method: str, path: str, response_code: int) -> None:
        self._statsd_client.count(
            CONSUL_REQUESTS_METRIC, 1, result=CONSUL_REQUEST_SUCCESSFUL_RESULT, type=str(response_code)
        )

    def on_http_request_failure(self, method: str, path: str, ex: BaseException) -> None:
        self._statsd_client.count(
            CONSUL_REQUESTS_METRIC, 1, result=CONSUL_REQUEST_FAILED_RESULT, type=type(ex).__name__
        )

    def on_http_request_invalid(self, method: str, path: str, response_code: int) -> None:
        self._statsd_client.count(
            CONSUL_REQUESTS_METRIC, 1, result=CONSUL_REQUEST_FAILED_RESULT, type=str(response_code)
        )
