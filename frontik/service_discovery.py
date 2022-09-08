import logging
import socket
import struct
import pickle
from random import shuffle

import time

import sys
from threading import Lock, Thread
from queue import Queue, Full

import asyncio
from consul.base import Check, Weight, KVCache, ConsistencyMode, HealthCache
from http_client import consul_parser, Upstream, options as http_client_options
from tornado.iostream import PipeIOStream, StreamClosedError

from frontik.consul_client import AsyncConsulClient, SyncConsulClient, ClientEventCallback
from frontik.integrations.statsd import Counters
from frontik.options import options
from frontik.version import version

DEFAULT_WEIGHT = 100
AUTO_RESOLVE_ADDRESS_VALUE = 'resolve'
MESSAGE_HEADER_MAGIC = b'T1uf31f'
MESSAGE_SIZE_STRUCT = '=Q'

CONSUL_REQUESTS_METRIC = "consul-client.request"
CONSUL_REQUEST_SUCCESSFUL_RESULT = "success"
CONSUL_REQUEST_FAILED_RESULT = "failure"

log = logging.getLogger('service_discovery')


def _get_service_address(options):
    if options.consul_service_address:
        if AUTO_RESOLVE_ADDRESS_VALUE == options.consul_service_address.lower():
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        return options.consul_service_address


def get_async_service_discovery(opts, statsd_client, *, event_loop=None):
    if not opts.consul_enabled:
        log.info('Consul disabled, skipping')
        return _AsyncStub()
    else:
        return _AsyncServiceDiscovery(opts, statsd_client, event_loop)


def get_sync_service_discovery(opts, statsd_client):
    if not opts.consul_enabled:
        log.info('Consul disabled, skipping')
        return _SyncStub()
    else:
        return _SyncServiceDiscovery(opts, statsd_client)


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
    def __init__(self, options, statsd_client, event_loop=None):
        self.options = options
        self.consul = AsyncConsulClient(host=options.consul_host,
                                        port=options.consul_port,
                                        loop=event_loop,
                                        client_event_callback=ConsulMetricsTracker(statsd_client))
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
                    'weights': Weight.weights(weight, 0),
                    'caller': self.service_name
                }
                if await self.consul.agent.service.register(self.service_name, **register_params):
                    log.info('Successfully registered service %s', register_params)
                else:
                    raise Exception(f'Failed to register {self.service_id}')

    async def deregister_service_and_close(self):
        if await self.consul.agent.service.deregister(self.service_id, self.service_name):
            log.info('Successfully deregistered service %s', self.service_id)
        else:
            log.info('Failed to deregister service %s normally', self.service_id)


class _SyncServiceDiscovery:
    def __init__(self, options, statsd_client):
        self.options = options
        self.consul = SyncConsulClient(host=options.consul_host,
                                       port=options.consul_port,
                                       client_event_callback=ConsulMetricsTracker(statsd_client))
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
            recurse=False,
            caller=self.service_name
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
            'weights': Weight.weights(weight, 0),
            'caller': self.service_name
        }
        if self.consul.agent.service.register(self.service_name, **register_params):
            log.info('Successfully registered service %s', register_params)
        else:
            raise Exception(f'Failed to register {register_params}')

    def deregister_service_and_close(self):
        self.kvCache.stop()
        if self.consul.agent.service.deregister(self.service_id, self.service_name):
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


class ConsulMetricsTracker(ClientEventCallback):

    def __init__(self, statsd_client):
        self._statsd_client = statsd_client
        self._request_counters = Counters()
        self._statsd_client.send_periodically(self._send_metrics)

    def on_http_request_success(self, method, path, response_code):
        self._request_counters.add(1, result=CONSUL_REQUEST_SUCCESSFUL_RESULT, type=response_code)

    def on_http_request_failure(self, method, path, ex):
        self._request_counters.add(1, result=CONSUL_REQUEST_FAILED_RESULT, type=type(ex).__name__)

    def on_http_request_invalid(self, method, path, response_code):
        self._request_counters.add(1, result=CONSUL_REQUEST_FAILED_RESULT, type=response_code)

    def _send_metrics(self):
        self._statsd_client.counters(CONSUL_REQUESTS_METRIC, self._request_counters)


class UpstreamUpdateListener:
    def __init__(self, http_client_factory, pipe):
        self.http_client_factory = http_client_factory
        self.stream = PipeIOStream(pipe)

        self.task = asyncio.create_task(self._process())

    async def _process(self):
        while True:
            try:
                await self.stream.read_until(MESSAGE_HEADER_MAGIC)
                size_header = await self.stream.read_bytes(8)
                size, = struct.unpack(MESSAGE_SIZE_STRUCT, size_header)
                data = await self.stream.read_bytes(size)
                log.debug('received upstreams length: %d', size)
                upstreams = pickle.loads(data)
                for upstream in upstreams:
                    self.http_client_factory.update_upstream(upstream)
            except StreamClosedError:
                log.exception('upstream update pipe is closed')
                sys.exit(1)
            except Exception:
                log.exception('failed to fetch upstream updates')


class UpstreamCaches:
    def __init__(self, children_pipes, upstreams, service_discovery=None):
        self._upstreams_config = {}
        self._upstreams_servers = {}
        self._upstream_list = options.upstreams
        self._datacenter_list = http_client_options.datacenters
        self._current_dc = http_client_options.datacenter
        self._allow_cross_dc_requests = http_client_options.http_client_allow_cross_datacenter_requests
        self._service_name = options.app
        self._upstreams = upstreams
        self._children_pipes = children_pipes
        self._lock = Lock()
        self._resend_dict = {}
        self._resend_notification = Queue(maxsize=1)
        self._resend_thread = Thread(target=self._resend, daemon=True)

        if service_discovery is not None:
            self._resend_thread.start()

            upstream_cache = KVCache(
                service_discovery.consul.kv,
                path='upstream/',
                watch_seconds=service_discovery.consul_weight_watch_seconds,
                backoff_delay_seconds=service_discovery.consul_cache_backoff_delay_seconds,
                total_timeout=service_discovery.consul_weight_total_timeout_sec,
                cache_initial_warmup_timeout=service_discovery.consul_cache_initial_warmup_timeout_sec,
                consistency_mode=service_discovery.consul_weight_consistency_mode,
                recurse=True,
                caller=self._service_name
            )
            upstream_cache.add_listener(self._update_upstreams_config, True)
            upstream_cache.start()

            for upstream in self._upstream_list:
                datacenters = self._datacenter_list if self._allow_cross_dc_requests else (self._current_dc,)
                for dc in datacenters:
                    health_cache = HealthCache(
                        service=upstream,
                        health_client=service_discovery.consul.health,
                        passing=True,
                        watch_seconds=service_discovery.consul_weight_watch_seconds,
                        backoff_delay_seconds=service_discovery.consul_cache_backoff_delay_seconds,
                        dc=dc,
                        caller=self._service_name
                    )
                    health_cache.add_listener(self._update_upstreams_service, True)
                    health_cache.start()

            if options.fail_start_on_empty_upstream:
                self._check_empty_upstreams_on_startup()

    def _check_empty_upstreams_on_startup(self):
        empty_upstreams = [k for k, v in self._upstreams.items() if not v.servers]
        if empty_upstreams:
            raise RuntimeError(
                f'failed startup application, because for next upstreams got empty servers: {empty_upstreams}'
            )

    def _update_upstreams_service(self, key, values):
        if values is not None:
            dc, servers = consul_parser.parse_consul_health_servers_data(values)
            log.info(f'update servers for upstream {key}, datacenter {dc}: [{",".join(str(s) for s in servers)}]')
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
        with self._lock:
            upstream = self._create_upstream(key)
            log.info(f'current servers for upstream {key}: [{",".join(str(s) for s in upstream.servers)}]')

            current_upstream = self._upstreams.get(key)

            if current_upstream is None:
                self._upstreams[key] = upstream
            else:
                current_upstream.update(upstream)

            if self._children_pipes:
                self.send_updates(upstream=upstream)

    def send_updates(self, upstream=None):
        upstreams = list(self._upstreams.values()) if upstream is None else [upstream]
        data = pickle.dumps(upstreams)
        log.debug('sending upstreams to all length: %d', len(data))
        for client_id, pipe in self._children_pipes.items():
            self._send_update(client_id, pipe, data)

    def _send_update(self, client_id, pipe, data):
        header_written = False
        try:
            pipe.write(MESSAGE_HEADER_MAGIC + struct.pack(MESSAGE_SIZE_STRUCT, len(data)))
            header_written = True
            pipe.write(data)
            pipe.flush()
        except BlockingIOError:
            log.warning(f'client {client_id} pipe blocked')
            if header_written:
                self._resend_dict[client_id] = True
                try:
                    self._resend_notification.put_nowait(True)
                except Full:
                    pass
        except Exception:
            log.exception(f'client {client_id} pipe write failed')

    def _combine_servers(self, key):
        servers_from_all_dc = []
        for dc in self._datacenter_list:
            servers = self._upstreams_servers.get(f'{key}-{dc}')
            if servers:
                servers_from_all_dc += servers
        return servers_from_all_dc

    def _resend(self):
        while True:
            self._resend_notification.get()
            time.sleep(1.0)

            with self._lock:
                data = pickle.dumps([self._create_upstream(key) for key in self._upstreams.keys()])
                clients = list(self._resend_dict.keys())
                log.debug('sending upstreams to %s length: %d', ','.join(clients), len(data))
                self._resend_dict.clear()

                for client_id in clients:
                    pipe = self._children_pipes.get(client_id, None)

                    if pipe is None:
                        continue

                    # writing 2 times to ensure fix of client reading pattern
                    self._send_update(client_id, pipe, data)
                    self._send_update(client_id, pipe, data)

    def _create_upstream(self, key):
        servers = self._combine_servers(key)
        shuffle(servers)
        return Upstream(key, self._upstreams_config.get(key, {}), servers)
