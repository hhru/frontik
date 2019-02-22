import asyncio
import json
import re
import socket
import time
from functools import partial
from random import shuffle, random

import pycurl
import logging
from lxml import etree
from tornado.escape import to_unicode
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.concurrent import Future
from tornado.curl_httpclient import CurlAsyncHTTPClient
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPResponse, HTTPError
from tornado.httputil import HTTPHeaders
from tornado.options import options

from frontik import media_types
from frontik.futures import AsyncGroup
from frontik.auth import DEBUG_AUTH_HEADER_NAME
from frontik.debug import DEBUG_HEADER_NAME, response_from_debug
from frontik.util import make_url, make_body, make_mfd


def _string_to_dict(s):
    return {name: value for (name, value) in (v.split('=') for v in s.split(' ') if v)}


http_client_logger = logging.getLogger('http_client')


class FailFastError(Exception):
    def __init__(self, failed_request: 'RequestResult'):
        self.failed_request = failed_request


class Server:
    @classmethod
    def from_config(cls, properties):
        params = {key: properties[key] for key in ('weight', 'rack', 'dc') if key in properties}
        return cls(properties.get('server'), **params)

    def __init__(self, address, weight=1, rack=None, dc=None):
        self.address = address.rstrip('/')
        self.weight = int(weight)
        self.rack = rack
        self.datacenter = dc

        self.current_requests = 0
        self.fails = 0
        self.requests = 0
        self.is_active = True
        self.join_strategy = None

        if self.weight < 1:
            raise ValueError('weight should not be less then 1')

    def update(self, server):
        if self.weight != server.weight:
            ratio = float(server.weight) / float(self.weight)
            self.requests = int(self.requests * ratio)

        self.weight = server.weight
        self.rack = server.rack
        self.datacenter = server.datacenter

    def disable(self):
        self.is_active = False

    def restore(self, join_strategy):
        self.fails = 0
        self.requests = 0
        self.is_active = True
        self.join_strategy = join_strategy


class RetryPolicy:
    _mapping = {
        'timeout': (599, False),
        'http_503': (503, False),
        'non_idempotent_503': (503, True),
    }

    def __init__(self, properties):
        self.statuses = dict(RetryPolicy._mapping.get(policy) for policy in properties.split(','))

    def check_retry(self, response, idempotent):
        if response.code == 599:
            error = str(response.error)
            if error.startswith('HTTP 599: Failed to connect') or error.startswith('HTTP 599: Connection timed out'):
                return True, True

        if response.code not in self.statuses:
            return False, False

        return idempotent or self.statuses.get(response.code), True


class Upstream:
    _single_host_upstream = None

    @classmethod
    def get_single_host_upstream(cls):
        if cls._single_host_upstream is not None:
            return cls._single_host_upstream

        cls._single_host_upstream = cls('single host upstream', {}, [Server('')])
        cls._single_host_upstream.balanced = False
        return cls._single_host_upstream

    @staticmethod
    def parse_config(config):
        configs = [_string_to_dict(v) for v in config.split('|')]

        upstream_config = configs.pop(0)
        servers = [Server.from_config(server_config) for server_config in configs if server_config]

        return upstream_config, servers

    def __init__(self, name, config, servers):
        self.name = name
        self.servers = []
        self.balanced = True

        self.update(config, servers)

    def borrow_server(self, exclude=None):
        min_index = None
        min_weights = None
        should_rescale_local_dc = True
        should_rescale_remote_dc = options.http_client_allow_cross_datacenter_requests

        if exclude is not None:
            tried_racks = {self.servers[index].rack for index in exclude if self.servers[index] is not None}
        else:
            tried_racks = None

        for index, server in enumerate(self.servers):
            if server is None or not server.is_active:
                continue

            is_different_datacenter = server.datacenter != options.datacenter

            if is_different_datacenter and not options.http_client_allow_cross_datacenter_requests:
                continue

            should_rescale = server.requests >= server.weight
            if is_different_datacenter:
                should_rescale_remote_dc = should_rescale_remote_dc and should_rescale
            else:
                should_rescale_local_dc = should_rescale_local_dc and should_rescale

            groups = (is_different_datacenter, tried_racks is not None and server.rack in tried_racks)

            if server.join_strategy is not None and not server.join_strategy.can_handle_request(server):
                current_load = float('inf')
            else:
                current_load = server.current_requests / float(server.weight)

            load = server.requests / float(server.weight)

            weights = (groups, current_load, load)

            if (exclude is None or index not in exclude) and (min_index is None or weights < min_weights):
                min_weights = weights
                min_index = index

        if min_index is None:
            return None, None, None, None

        if should_rescale_local_dc or should_rescale_remote_dc:
            for server in self.servers:
                if server is not None and server.is_active:
                    is_same_dc = server.datacenter == options.datacenter
                    if (should_rescale_local_dc and is_same_dc) or (should_rescale_remote_dc and not is_same_dc):
                        server.requests -= server.weight

        server = self.servers[min_index]
        server.requests += 1
        server.current_requests += 1

        if server.join_strategy is not None:
            server.join_strategy.handle_request()

            if server.join_strategy.is_complete():
                max_load = max(server.requests / float(server.weight) for server in self.servers
                               if server is not None and server.is_active)
                server.requests = int(server.weight * max_load)
                server.join_strategy = None

        return min_index, server.address, server.rack, server.datacenter

    def return_server(self, index, error=False):
        server = self.servers[index]
        if server is not None:
            if server.current_requests > 0:
                server.current_requests -= 1

            if error:
                server.fails += 1

                if self.max_fails != 0 and server.fails >= self.max_fails:
                    self._disable_server(server)
            else:
                server.fails = 0

    def _disable_server(self, server):
        http_client_logger.info('disabling server %s for upstream %s', server.address, self.name)
        server.disable()
        IOLoop.current().add_timeout(IOLoop.current().time() + self.fail_timeout, partial(self._restore_server, server))

    def _restore_server(self, server):
        http_client_logger.info('restoring server %s for upstream %s', server.address, self.name)
        server.restore(self.get_join_strategy())

    def update(self, config, servers):
        if not servers:
            raise ValueError('server list should not be empty')

        self.max_tries = int(config.get('max_tries', options.http_client_default_max_tries))
        self.max_fails = int(config.get('max_fails', options.http_client_default_max_fails))
        self.fail_timeout = float(config.get('fail_timeout_sec', options.http_client_default_fail_timeout_sec))
        self.max_timeout_tries = int(config.get('max_timeout_tries', options.http_client_default_max_timeout_tries))
        self.connect_timeout = float(config.get('connect_timeout_sec', options.http_client_default_connect_timeout_sec))
        self.request_timeout = float(config.get('request_timeout_sec', options.http_client_default_request_timeout_sec))

        slow_start_interval = float(config.get('slow_start_interval_sec', 0))
        slow_start_requests = int(config.get('slow_start_requests', 0))

        self.get_join_strategy = lambda: DefaultJoinStrategy
        if slow_start_interval != 0 or slow_start_requests != 0:
            self.get_join_strategy = partial(DelayedSlowStartJoinStrategy, slow_start_interval, slow_start_requests)

        self.retry_policy = RetryPolicy(config.get('retry_policy', options.http_client_default_retry_policy))

        mapping = {server.address: server for server in servers}

        for index, server in enumerate(self.servers):
            if server is None:
                continue

            changed = mapping.get(server.address)
            if changed is None:
                self.servers[index] = None
            else:
                del mapping[server.address]
                if server.is_active and server.datacenter != changed.datacenter:
                    server.restore(self.get_join_strategy())
                server.update(changed)

        for server in servers:
            if server.address in mapping:
                self._add_server(server)

    def _add_server(self, server):
        server.restore(self.get_join_strategy())

        for index, s in enumerate(self.servers):
            if s is None:
                self.servers[index] = server
                return

        self.servers.append(server)

    def __str__(self):
        return '[{}]'.format(','.join(server.address for server in self.servers if server is not None))


class DefaultJoinStrategy:
    @staticmethod
    def is_complete():
        return True

    @staticmethod
    def can_handle_request(server):
        return True

    @staticmethod
    def handle_request():
        pass

    def __repr__(self):
        return '<DefaultJoinStrategy>'


class DelayedSlowStartJoinStrategy:
    def __init__(self, slow_start_interval, slow_start_requests):
        self.initial_delay_end_time = time.time() + random() * slow_start_interval
        self.slow_start_requests = slow_start_requests

    def is_complete(self):
        return time.time() > self.initial_delay_end_time and self.slow_start_requests <= 0

    def can_handle_request(self, server):
        if server.current_requests > 0:
            return False

        if time.time() < self.initial_delay_end_time:
            return False

        return True

    def handle_request(self):
        self.slow_start_requests -= 1

    def __repr__(self):
        return '<DelayedSlowStartJoinStrategy(initial_delay_end_time={}, slow_start_requests={})>'.format(
            self.initial_delay_end_time, self.slow_start_requests)


class BalancedHttpRequest:
    def __init__(self, host, upstream, uri, name, method='GET', data=None, headers=None, files=None, content_type=None,
                 connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                 follow_redirects=True, idempotent=True):
        self.uri = uri if uri.startswith('/') else '/' + uri
        self.upstream = upstream
        self.name = name
        self.method = method
        self.headers = HTTPHeaders() if headers is None else HTTPHeaders(headers)
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self.follow_redirects = follow_redirects
        self.idempotent = idempotent
        self.body = None
        self.first_status = None
        self.last_request = None

        if request_timeout is not None and max_timeout_tries is None:
            max_timeout_tries = options.http_client_default_max_timeout_tries

        if self.connect_timeout is None:
            self.connect_timeout = self.upstream.connect_timeout
        if self.request_timeout is None:
            self.request_timeout = self.upstream.request_timeout
        if max_timeout_tries is None:
            max_timeout_tries = self.upstream.max_timeout_tries

        self.connect_timeout *= options.timeout_multiplier
        self.request_timeout *= options.timeout_multiplier

        if self.method == 'POST':
            if files:
                self.body, content_type = make_mfd(data, files)
            else:
                self.body = make_body(data)

            if content_type is None:
                content_type = self.headers.get('Content-Type', media_types.APPLICATION_FORM_URLENCODED)

            self.headers['Content-Length'] = str(len(self.body))
        elif self.method == 'PUT':
            self.body = make_body(data)
        else:
            self.uri = make_url(self.uri, **({} if data is None else data))

        if content_type is not None:
            self.headers['Content-Type'] = content_type

        self.tries_left = self.upstream.max_tries
        self.request_time_left = self.request_timeout * max_timeout_tries
        self.tried_hosts = None
        self.current_host = host.rstrip('/')
        self.current_server_index = None
        self.current_rack = None
        self.current_datacenter = None

    def make_request(self):
        if self.upstream.balanced:
            index, host, rack, datacenter = self.upstream.borrow_server(self.tried_hosts)

            self.current_server_index = index
            self.current_host = host
            self.current_rack = rack
            self.current_datacenter = datacenter

        request = HTTPRequest(
            url=(self.current_host if self.backend_available() else self.upstream.name) + self.uri,
            body=self.body,
            method=self.method,
            headers=self.headers,
            follow_redirects=self.follow_redirects,
            connect_timeout=self.connect_timeout,
            request_timeout=self.request_timeout,
        )

        if options.http_proxy_host is not None:
            request.proxy_host = options.http_proxy_host
            request.proxy_port = options.http_proxy_port

        self.last_request = request
        return self.last_request

    def backend_available(self):
        return self.current_host is not None

    def get_host(self):
        return self.upstream.name if self.upstream.balanced else self.current_host

    def check_retry(self, response):
        self.tries_left -= 1
        self.request_time_left -= response.request_time

        if self.upstream.balanced:
            do_retry, error = self.upstream.retry_policy.check_retry(response, self.idempotent)

            if self.current_server_index is not None:
                self.upstream.return_server(self.current_server_index, error)
        else:
            do_retry, error = False, False

        do_retry = do_retry and self.tries_left > 0 and self.request_time_left > 0

        if do_retry:
            if self.tried_hosts is None:
                self.first_status = response.code
                self.tried_hosts = set()

            self.tried_hosts.add(self.current_server_index)

        return do_retry

    def pop_last_request(self):
        request = self.last_request
        self.last_request = None
        return request

    def get_retries_count(self):
        return len(self.tried_hosts) if self.tried_hosts else 0


class HttpClientFactory:
    def __init__(self, upstreams):
        AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient', max_clients=options.max_http_clients)

        self.tornado_http_client = AsyncHTTPClient()

        if options.max_http_clients_connects is not None:
            self.tornado_http_client._multi.setopt(pycurl.M_MAXCONNECTS, options.max_http_clients_connects)

        self.upstreams = {}

        for name, upstream in upstreams.items():
            servers = [Server.from_config(s) for s in upstream['servers']]
            shuffle(servers)
            self.register_upstream(name, upstream['config'], servers)

    def get_http_client(self, handler, modify_http_request_hook):
        return HttpClient(handler, self.tornado_http_client, modify_http_request_hook,
                          self.upstreams, handler.statsd_client, getattr(handler, 'influxdb_client', None))

    def update_upstream(self, name, config):
        if config is None:
            self.register_upstream(name, {}, [])
            return

        upstream_config, servers = Upstream.parse_config(config)
        shuffle(servers)
        self.register_upstream(name, upstream_config, servers)

    def register_upstream(self, name, upstream_config, servers):
        upstream = self.upstreams.get(name)

        if not servers:
            if upstream is not None:
                del self.upstreams[name]
                http_client_logger.info('delete %s upstream', name)
            return

        if upstream is None:
            upstream = Upstream(name, upstream_config, servers)
            self.upstreams[name] = upstream
            http_client_logger.info('add %s upstream: %s', name, str(upstream))
            return

        upstream.update(upstream_config, servers)
        http_client_logger.info('update %s upstream: %s', name, str(upstream))


class HttpClient:
    def __init__(self, handler, http_client_impl, modify_http_request_hook, upstreams, statsd_client, influxdb_client):
        self.handler = handler
        self.modify_http_request_hook = modify_http_request_hook
        self.http_client_impl = http_client_impl
        self.upstreams = upstreams
        self.hostname = socket.gethostname()
        self.statsd_client = statsd_client
        self.influxdb_client = influxdb_client

        self.influxdb_metrics_enabled = (
            self.influxdb_client is not None and
            options.influxdb_metrics_db is not None and options.influxdb_metrics_rp is not None
        )
        self.influxdb_heartbeat_enabled = (
            self.influxdb_client is not None and
            options.influxdb_heartbeat_db is not None and options.influxdb_heartbeat_rp is not None
        )

        if self.influxdb_heartbeat_enabled:
            PeriodicCallback(self._influx_heartbeat, options.influxdb_heartbeat_period_ms).start()

    def get_upstream(self, host):
        return self.upstreams.get(host, Upstream.get_single_host_upstream())

    def group(self, futures, callback=None, name=None):
        group_future = Future()
        results_holder = {}

        def group_callback():
            if callable(callback):
                callback(results_holder)
            group_future.set_result(results_holder)

        def future_callback(name, future):
            results_holder[name] = future.result()

        async_group = AsyncGroup(self.handler.finish_group.add(self.handler.check_finished(group_callback)), name=name)

        for name, future in futures.items():
            if future.done():
                future_callback(name, future)
            else:
                self.handler.add_future(future, async_group.add(partial(future_callback, name)))

        async_group.try_finish_async()

        return group_future

    def get_url(self, host, uri, *, name=None, data=None, headers=None, follow_redirects=True,
                connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                callback=None, add_to_finish_group=True, parse_response=True, parse_on_error=False, fail_fast=False):

        request = BalancedHttpRequest(host, self.get_upstream(host), uri, name, 'GET', data, headers,
                                      None, None, connect_timeout, request_timeout, max_timeout_tries,
                                      follow_redirects)

        return self._fetch_with_retry(
            request, callback, add_to_finish_group, parse_response, parse_on_error, fail_fast
        )

    def head_url(self, host, uri, *, name=None, data=None, headers=None, follow_redirects=True,
                 connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                 callback=None, add_to_finish_group=True, fail_fast=False):

        request = BalancedHttpRequest(host, self.get_upstream(host), uri, name, 'HEAD', data, headers,
                                      None, None, connect_timeout, request_timeout, max_timeout_tries,
                                      follow_redirects)

        return self._fetch_with_retry(request, callback, add_to_finish_group, False, False, fail_fast)

    def post_url(self, host, uri, *,
                 name=None, data='', headers=None, files=None, content_type=None, follow_redirects=True,
                 connect_timeout=None, request_timeout=None, max_timeout_tries=None, idempotent=False,
                 callback=None, add_to_finish_group=True, parse_response=True, parse_on_error=False, fail_fast=False):

        request = BalancedHttpRequest(host, self.get_upstream(host), uri, name, 'POST', data, headers,
                                      files, content_type, connect_timeout, request_timeout, max_timeout_tries,
                                      follow_redirects, idempotent)

        return self._fetch_with_retry(
            request, callback, add_to_finish_group, parse_response, parse_on_error, fail_fast
        )

    def put_url(self, host, uri, *, name=None, data='', headers=None, content_type=None,
                connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                callback=None, add_to_finish_group=True, parse_response=True, parse_on_error=False, fail_fast=False):

        request = BalancedHttpRequest(host, self.get_upstream(host), uri, name, 'PUT', data, headers,
                                      None, content_type, connect_timeout, request_timeout, max_timeout_tries)

        return self._fetch_with_retry(
            request, callback, add_to_finish_group, parse_response, parse_on_error, fail_fast
        )

    def delete_url(self, host, uri, *, name=None, data=None, headers=None, content_type=None,
                   connect_timeout=None, request_timeout=None, max_timeout_tries=None,
                   callback=None, add_to_finish_group=True, parse_response=True, parse_on_error=False, fail_fast=False):

        request = BalancedHttpRequest(host, self.get_upstream(host), uri, name, 'DELETE', data, headers,
                                      None, content_type, connect_timeout, request_timeout, max_timeout_tries)

        return self._fetch_with_retry(
            request, callback, add_to_finish_group, parse_response, parse_on_error, fail_fast
        )

    def _influx_heartbeat(self):
        asyncio.get_event_loop().create_task(
            self.influxdb_client.write(
                'heartbeat,app={app},dc={dc},hostname={hostname} ts={ts}'.format(
                    app=self.handler.application.app,
                    dc=options.datacenter,
                    hostname=self.hostname,
                    ts=int(time.time() * 1000)
                ),
                db=options.influxdb_heartbeat_db,
                rp=options.influxdb_heartbeat_rp
            )
        )

    def _fetch_with_retry(self, balanced_request, callback, add_to_finish_group, parse_response, parse_on_error,
                          fail_fast):
        future = Future()

        def request_finished_callback(response):
            if response is None:
                return

            if balanced_request.tried_hosts is not None:
                self.statsd_client.count('http.client.retries', 1,
                                         upstream=balanced_request.get_host(),
                                         server=balanced_request.current_host,
                                         datacenter=balanced_request.current_datacenter,
                                         first_upstream_status=balanced_request.first_status,
                                         tries=len(balanced_request.tried_hosts),
                                         status=response.code)

            if self.handler.is_finished():
                http_client_logger.warning('page was already finished, {} ignored'.format(callback))
                return

            result = self._parse_response(response, parse_response, parse_on_error)
            result.request = balanced_request
            result.name = balanced_request.name

            if callable(callback):
                callback(result.data, result.response)

            if fail_fast and (result.response.error or result.data_parse_error is not None):
                raise FailFastError(result)
            else:
                future.set_result(result)

        if add_to_finish_group and not self.handler.is_finished():
            request_finished_callback = self.handler.finish_group.add(request_finished_callback)

        def retry_callback(response=None):
            if response is None:
                request_finished_callback(None)
                return

            if isinstance(response.error, Exception) and not isinstance(response.error, HTTPError):
                raise response.error

            request = balanced_request.pop_last_request()
            retries_count = balanced_request.get_retries_count()

            response, debug_extra = self._unwrap_debug(balanced_request, request, response, retries_count)
            do_retry = balanced_request.check_retry(response)

            self._log_response(balanced_request, response, retries_count, do_retry, debug_extra)
            self.statsd_client.stack()
            self.statsd_client.count(
                'http.client.requests', 1,
                upstream=balanced_request.get_host(),
                datacenter=balanced_request.current_datacenter,
                final='false' if do_retry else 'true',
                status=response.code
            )
            self.statsd_client.time(
                'http.client.request.time',
                int(response.request_time * 1000),
                datacenter=balanced_request.current_datacenter,
                upstream=balanced_request.get_host()
            )
            self.statsd_client.flush()

            if self.influxdb_metrics_enabled and response.code >= 500:
                asyncio.get_event_loop().create_task(
                    self.influxdb_client.write(
                        'request,app={app},dc={dc},final={final},server={server},status={status},upstream={upstream}'
                        ' response_time={time}'.format(
                            app=self.handler.application.app,
                            dc=balanced_request.current_datacenter,
                            final='false' if do_retry else 'true',
                            server=balanced_request.current_host,
                            status=response.code,
                            upstream=balanced_request.get_host(),
                            time=int(response.request_time * 1000)
                        ),
                        db=options.influxdb_metrics_db,
                        rp=options.influxdb_metrics_rp
                    )
                )

            if do_retry:
                self._fetch(balanced_request, retry_callback)
                return

            request_finished_callback(response)

        self.modify_http_request_hook(balanced_request)
        self._fetch(balanced_request, retry_callback)

        return future

    def _fetch(self, balanced_request, callback):
        if self.handler.is_finished():
            http_client_logger.warning(
                'attempted to make http request to %s %s when page is finished, ignoring',
                balanced_request.get_host(),
                balanced_request.uri
            )

            callback(None)
            return

        request = balanced_request.make_request()

        if not balanced_request.backend_available():
            response = HTTPResponse(request, 502,
                                    error=HTTPError(502, 'No backend available for ' + balanced_request.get_host()),
                                    request_time=0)
            IOLoop.current().add_callback(callback, response)
            return

        if self.handler.debug_mode.pass_debug:
            request.headers[DEBUG_HEADER_NAME] = 'true'

            # debug_timestamp is added to avoid caching of debug responses
            request.url = make_url(request.url, debug_timestamp=int(time.time()))

            for header_name in ('Authorization', DEBUG_AUTH_HEADER_NAME):
                authorization = self.handler.request.headers.get(header_name)
                if authorization is not None:
                    request.headers[header_name] = authorization

        request.headers['X-Request-Id'] = self.handler.request_id

        if isinstance(self.http_client_impl, CurlAsyncHTTPClient):
            request.prepare_curl_callback = partial(
                self._prepare_curl_callback, next_callback=request.prepare_curl_callback
            )

        self.http_client_impl.fetch(request, callback, raise_error=False)

    def _prepare_curl_callback(self, curl, next_callback):
        curl.setopt(pycurl.NOSIGNAL, 1)

        if callable(next_callback):
            next_callback(curl)

    def _unwrap_debug(self, balanced_request, request, response, retries_count):
        debug_extra = {}

        try:
            if response.headers.get(DEBUG_HEADER_NAME):
                debug_response = response_from_debug(request, response)
                if debug_response is not None:
                    debug_xml, response = debug_response
                    debug_extra['_debug_response'] = debug_xml

            if self.handler.debug_mode.enabled:
                debug_extra.update({'_response': response, '_request': request,
                                    '_request_retry': retries_count,
                                    '_rack': balanced_request.current_rack,
                                    '_datacenter': balanced_request.current_datacenter,
                                    '_balanced_request': balanced_request})
        except Exception:
            http_client_logger.exception('Cannot get response from debug')

        return response, debug_extra

    def _log_response(self, balanced_request, response, retries_count, do_retry, debug_extra):
        log_message = 'got {code}{size}{retry}, {do_retry} {method} {url} in {time:.2f}ms'.format(
            code=response.code,
            method=balanced_request.method,
            url=response.effective_url,
            size=' {0} bytes'.format(len(response.body)) if response.body is not None else '',
            retry=' retry {}'.format(retries_count) if retries_count > 0 else '',
            do_retry='retrying' if do_retry else 'final',
            time=response.request_time * 1000
        )

        log_method = http_client_logger.warning if response.code >= 500 else http_client_logger.info
        log_method(log_message, extra=debug_extra)

        if response.code == 599:
            timings_info = ('{}={}ms'.format(stage, int(timing * 1000)) for stage, timing in response.time_info.items())
            http_client_logger.info('Curl timings: %s', ' '.join(timings_info))

    def _parse_response(self, response, parse_response, parse_on_error):
        result = RequestResult()
        result.response = response

        if response.error and not parse_on_error:
            data_or_error = DataParseError(reason=str(response.error), code=response.code)
        elif not parse_response or response.code == 204:
            data_or_error = response.body
        else:
            data_or_error = None
            content_type = response.headers.get('Content-Type', '')
            for k, v in DEFAULT_REQUEST_TYPES.items():
                if k.search(content_type):
                    data_or_error = v(result.response)
                    break

        if isinstance(data_or_error, DataParseError):
            result.data_parse_error = data_or_error
        else:
            result.data = data_or_error

        return result


class DataParseError:
    __slots__ = ('attrs',)

    def __init__(self, **attrs):
        self.attrs = attrs


class RequestResult:
    __slots__ = ('name', 'request', 'data', 'data_parse_error', 'response')

    def __init__(self):
        self.name = None
        self.request = None
        self.data = None
        self.data_parse_error = None
        self.response = None

    def to_dict(self):
        if isinstance(self.data_parse_error, DataParseError):
            return {
                'error': {k: v for k, v in self.data_parse_error.attrs.items()}
            }

        return self.data if isinstance(self.data, (dict, list)) else None

    def to_etree_element(self):
        if isinstance(self.data_parse_error, DataParseError):
            return etree.Element('error', **{k: str(v) for k, v in self.data_parse_error.attrs.items()})

        return self.data if isinstance(self.data, etree._Element) else None


def _parse_response(response, parser, response_type):
    try:
        return parser(response.body)
    except Exception:
        _preview_len = 100

        if response.body is None:
            body_preview = None
        elif len(response.body) > _preview_len:
            body_preview = response.body[:_preview_len]
        else:
            body_preview = response.body

        if body_preview is not None:
            try:
                body_preview = 'excerpt: {}'.format(to_unicode(body_preview))
            except Exception:
                body_preview = 'could not be converted to unicode, excerpt: {}'.format(str(body_preview))
        else:
            body_preview = 'is None'

        http_client_logger.exception(
            'failed to parse %s response from %s, body %s',
            response_type, response.effective_url, body_preview
        )

        return DataParseError(reason='invalid {}'.format(response_type))


_xml_parser = etree.XMLParser(strip_cdata=False)
_parse_response_xml = partial(
    _parse_response, parser=lambda body: etree.fromstring(body, parser=_xml_parser), response_type='xml'
)

_parse_response_json = partial(_parse_response, parser=json.loads, response_type='json')

_parse_response_text = partial(_parse_response, parser=to_unicode, response_type='text')

DEFAULT_REQUEST_TYPES = {
    re.compile('.*xml.?'): _parse_response_xml,
    re.compile('.*json.?'): _parse_response_json,
    re.compile('.*text/plain.?'): _parse_response_text,
}
