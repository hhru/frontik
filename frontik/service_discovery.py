import itertools
import logging
import socket
from random import shuffle
from threading import Lock
from typing import Callable, Optional, Union

from consul.base import Check, ConsistencyMode, HealthCache, KVCache, Weight
from http_client import consul_parser
from http_client import options as http_options
from http_client.balancing import Server, Upstream

from frontik.consul_client import ClientEventCallback, SyncConsulClient
from frontik.integrations.statsd import Counters, StatsDClient, StatsDClientStub
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
        check_host = address if address else '127.0.0.1'
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
        msg = 'options node_name must be defined'
        raise RuntimeError(msg)
    return node_name


class UpstreamManager:
    def __init__(
        self,
        upstreams: dict[str, Upstream],
        statsd_client: Union[StatsDClient, StatsDClientStub],
        upstreams_lock: Optional[Lock],
        send_to_all_workers: Optional[Callable],
        with_consul: bool,
    ) -> None:
        self.with_consul: bool = with_consul
        self._upstreams_config: dict[str, dict] = {}
        self._upstreams_servers: dict[str, list[Server]] = {}

        self._upstreams = upstreams
        self._upstreams_lock = upstreams_lock or Lock()  # should be used when access self._upstreams
        self._send_to_all_workers = send_to_all_workers

        if not self.with_consul:
            log.info('Consul disabled, skipping')
            return

        self.consul = SyncConsulClient(
            host=options.consul_host,
            port=options.consul_port,
            client_event_callback=ConsulMetricsTracker(statsd_client),
        )
        self._service_name = options.app
        self.hostname = _get_hostname_or_raise(options.node_name)
        self.service_id = _make_service_id(options, service_name=self._service_name, hostname=self.hostname)
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
            caller=self._service_name,
        )
        self.kvCache.add_listener(self._update_register, False)

        upstream_cache = KVCache(
            self.consul.kv,
            path='upstream/',
            watch_seconds=self.consul_weight_watch_seconds,
            backoff_delay_seconds=self.consul_cache_backoff_delay_seconds,
            total_timeout=self.consul_weight_total_timeout_sec,
            cache_initial_warmup_timeout=self.consul_cache_initial_warmup_timeout_sec,
            consistency_mode=self.consul_weight_consistency_mode,
            recurse=True,
            caller=self._service_name,
        )
        upstream_cache.add_listener(self._update_upstreams_config, True)
        upstream_cache.start()

        allow_cross_dc = http_options.http_client_allow_cross_datacenter_requests
        datacenters = http_options.datacenters if allow_cross_dc else (http_options.datacenter,)
        for upstream, dc in itertools.product(options.upstreams, datacenters):
            health_cache = HealthCache(
                service=upstream,
                health_client=self.consul.health,
                passing=True,
                watch_seconds=self.consul_weight_watch_seconds,
                backoff_delay_seconds=self.consul_cache_backoff_delay_seconds,
                dc=dc,
                caller=self._service_name,
            )
            health_cache.add_listener(self._update_upstreams_service, True)
            health_cache.start()

        if options.fail_start_on_empty_upstream:
            self._check_empty_upstreams_on_startup()

    def _update_register(self, key, new_value):
        weight = _get_weight_or_default(new_value)
        self._sync_register(weight)

    def register_service(self) -> None:
        if not self.with_consul:
            return

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
            'caller': self._service_name,
        }
        if self.consul.agent.service.register(self._service_name, **register_params):
            log.info('Successfully registered service %s', register_params)
        else:
            raise Exception(f'Failed to register {register_params}')

    def deregister_service_and_close(self) -> None:
        if not self.with_consul:
            return

        self.kvCache.stop()
        if self.consul.agent.service.deregister(self.service_id, self._service_name):
            log.info('Successfully deregistered service %s', self.service_id)
        else:
            log.info('Failed to deregister service %s normally', self.service_id)

    def get_upstreams(self) -> dict[str, Upstream]:
        return self._upstreams

    def _check_empty_upstreams_on_startup(self) -> None:
        empty_upstreams = [k for k, v in self._upstreams.items() if not v.servers]
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

    def _update_upstreams_config(self, key, values):
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
            self._send_to_all_workers(upstreams)

    def _create_upstream(self, key: str) -> Upstream:
        servers = self._combine_servers(key)
        shuffle(servers)
        return Upstream(key, self._upstreams_config.get(key, {}), servers)

    def _combine_servers(self, key: str) -> list[Server]:
        servers_from_all_dc = []
        for dc in http_options.datacenters:
            servers = self._upstreams_servers.get(f'{key}-{dc}')
            if servers:
                servers_from_all_dc += servers
        return servers_from_all_dc

    def update_upstreams(self, upstreams: list[Upstream]) -> None:
        for upstream in upstreams:
            self._update_upstream(upstream)

    def _update_upstream(self, upstream: Upstream) -> None:
        current_upstream = self._upstreams.get(upstream.name)

        if current_upstream is None:
            shuffle(upstream.servers)
            self._upstreams[upstream.name] = upstream
            log.debug('add %s upstream: %s', upstream.name, str(upstream))
            return

        current_upstream.update(upstream)
        log.debug('update %s upstream: %s', upstream.name, str(upstream))


class ConsulMetricsTracker(ClientEventCallback):
    def __init__(self, statsd_client: Union[StatsDClient, StatsDClientStub]) -> None:
        self._statsd_client = statsd_client
        self._request_counters = Counters()
        self._statsd_client.send_periodically(self._send_metrics)

    def on_http_request_success(self, method: str, path: str, response_code: int) -> None:
        self._request_counters.add(1, result=CONSUL_REQUEST_SUCCESSFUL_RESULT, type=response_code)

    def on_http_request_failure(self, method: str, path: str, ex: BaseException) -> None:
        self._request_counters.add(1, result=CONSUL_REQUEST_FAILED_RESULT, type=type(ex).__name__)

    def on_http_request_invalid(self, method: str, path: str, response_code: int) -> None:
        self._request_counters.add(1, result=CONSUL_REQUEST_FAILED_RESULT, type=response_code)

    def _send_metrics(self):
        self._statsd_client.counters(CONSUL_REQUESTS_METRIC, self._request_counters)
