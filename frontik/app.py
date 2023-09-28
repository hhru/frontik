from __future__ import annotations
import asyncio
import importlib
import multiprocessing
from multiprocessing.sharedctypes import Synchronized
import sys
import time
import traceback
from functools import partial
from typing import TYPE_CHECKING
import logging

import aiohttp
import tornado
from lxml import etree
from tornado import httputil
from tornado.web import Application, RequestHandler, HTTPError
from http_client import HttpClientFactory, options as http_client_options, AIOHttpClientWrapper
from http_client.balancing import RequestBalancerBuilder, UpstreamManager, Upstream

import frontik.producers.json_producer
import frontik.producers.xml_producer
from frontik import integrations, media_types, request_context
from frontik.integrations.statsd import create_statsd_client
from frontik.debug import DebugTransform
from frontik.handler import ErrorHandler
from frontik.loggers import CUSTOM_JSON_EXTRA, JSON_REQUESTS_LOGGER
from frontik.options import options
from frontik.routing import FileMappingRouter, FrontikRouter
from frontik.service_discovery import get_sync_service_discovery, get_async_service_discovery, UpstreamCaches
from frontik.util import generate_uniq_timestamp_request_id, check_request_id
from frontik.version import version as frontik_version

app_logger = logging.getLogger('http_client')

if TYPE_CHECKING:
    from typing import Optional, Callable, Any
    from tornado.httputil import HTTPServerRequest
    from aiokafka import AIOKafkaProducer
    from frontik.integrations.statsd import StatsDClient, StatsDClientStub
    from frontik.service_discovery import UpstreamUpdateListener


class VersionHandler(RequestHandler):
    def get(self):
        self.application: FrontikApplication
        self.set_header('Content-Type', 'text/xml')
        self.write(
            etree.tostring(get_frontik_and_apps_versions(self.application), encoding='utf-8', xml_declaration=True)
        )


class StatusHandler(RequestHandler):
    def get(self):
        self.application: FrontikApplication
        self.set_header('Content-Type', media_types.APPLICATION_JSON)
        self.finish(self.application.get_current_status())


class PydevdHandler(RequestHandler):
    def get(self):
        if hasattr(sys, 'gettrace') and sys.gettrace() is not None:
            self.already_tracing_page()
            return

        try:
            debugger_ip = self.get_argument('debugger_ip', self.request.remote_ip)
            debugger_port = self.get_argument('debugger_port', '32223')
            self.settrace(debugger_ip, int(debugger_port))
            self.trace_page(debugger_ip, debugger_port)

        except BaseException:
            self.error_page()

    def settrace(self, debugger_ip: str | None, debugger_port: int) -> None:
        import pydevd

        pydevd.settrace(debugger_ip, port=debugger_port, stdoutToServer=True, stderrToServer=True, suspend=False)

    def trace_page(self, ip: str | None, port: str) -> None:
        self.set_header('Content-Type', media_types.TEXT_PLAIN)
        self.finish(f'Connected to debug server at {ip}:{port}')

    def already_tracing_page(self) -> None:
        self.set_header('Content-Type', media_types.TEXT_PLAIN)
        self.finish('App is already in tracing mode, try to restart service')

    def error_page(self) -> None:
        self.set_header('Content-Type', media_types.TEXT_PLAIN)
        self.finish(traceback.format_exc())


class FrontikApplication(Application):
    request_id = ''

    class DefaultConfig:
        pass

    def __init__(self, **settings: Any) -> None:
        self.start_time = time.time()

        tornado_settings = settings.get('tornado_settings')
        if tornado_settings is None:
            tornado_settings = {}

        self.config = self.application_config()
        self.app = settings.get('app')
        self.app_module = settings.get('app_module')
        self.app_root: str = settings.get('app_root')  # type: ignore

        self.xml = frontik.producers.xml_producer.XMLProducerFactory(self)
        self.json = frontik.producers.json_producer.JsonProducerFactory(self)

        self.available_integrations: list[integrations.Integration] = []
        self.tornado_http_client: Optional[AIOHttpClientWrapper] = None
        self.http_client_factory: HttpClientFactory = None  # type: ignore
        self.upstream_manager: UpstreamManager = None
        self.upstreams: dict[str, Upstream] = {}
        self.children_pipes: dict[int, Any] = {}
        self.upstream_update_listener: UpstreamUpdateListener = None  # type: ignore
        self.router = FrontikRouter(self)
        self.init_workers_count_down: Synchronized = multiprocessing.Value('i', options.workers)  # type: ignore

        core_handlers: list[Any] = [
            (r'/version/?', VersionHandler),
            (r'/status/?', StatusHandler),
            (r'.*', self.router),
        ]

        if options.debug:
            core_handlers.insert(0, (r'/pydevd/?', PydevdHandler))

        self.statsd_client: StatsDClient|StatsDClientStub = create_statsd_client(options, self)
        sync_service_discovery = get_sync_service_discovery(options, self.statsd_client)
        self.service_discovery_client = (
            get_async_service_discovery(options, self.statsd_client) if options.workers == 1 else sync_service_discovery
        )
        self.upstream_caches = (
            UpstreamCaches(self.children_pipes, self.upstreams, sync_service_discovery)
            if options.consul_enabled
            else UpstreamCaches(self.children_pipes, self.upstreams)
        )

        super().__init__(core_handlers, **tornado_settings)

    async def init(self) -> None:
        self.transforms.insert(0, partial(DebugTransform, self))  # type: ignore

        self.available_integrations, integration_futures = integrations.load_integrations(self)
        await asyncio.gather(*[future for future in integration_futures if future])

        self.tornado_http_client = AIOHttpClientWrapper()

        kafka_cluster = options.http_client_metrics_kafka_cluster
        send_metrics_to_kafka = kafka_cluster and kafka_cluster in options.kafka_clusters

        if kafka_cluster and kafka_cluster not in options.kafka_clusters:
            app_logger.warning(
                'kafka cluster for http client metrics "%s" is not present in "kafka_clusters" option, '
                'metrics will be disabled',
                kafka_cluster,
            )
        else:
            app_logger.info('kafka metrics are %s', 'enabled' if send_metrics_to_kafka else 'disabled')

        kafka_producer = self.get_kafka_producer(kafka_cluster) if send_metrics_to_kafka and kafka_cluster is not None else None

        self.upstream_manager = UpstreamManager(self.upstreams)
        request_balancer_builder = RequestBalancerBuilder(
            self.upstream_manager, statsd_client=self.statsd_client, kafka_producer=kafka_producer
        )
        self.http_client_factory = HttpClientFactory(self.app, self.tornado_http_client, request_balancer_builder)

    def find_handler(self, request, **kwargs):
        request_id = request.headers.get('X-Request-Id')
        if request_id is None:
            request_id = FrontikApplication.next_request_id()
        if options.validate_request_id:
            check_request_id(request_id)

        def wrapped_in_context(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                token = request_context.initialize(request, request_id)

                try:
                    return func(*args, **kwargs)
                finally:
                    request_context.reset(token)

            return wrapper

        delegate: httputil.HTTPMessageDelegate = wrapped_in_context(super().find_handler)(request, **kwargs)
        delegate.headers_received = wrapped_in_context(delegate.headers_received)  # type: ignore
        delegate.data_received = wrapped_in_context(delegate.data_received)  # type: ignore
        delegate.finish = wrapped_in_context(delegate.finish)  # type: ignore
        delegate.on_connection_close = wrapped_in_context(delegate.on_connection_close)  # type: ignore

        return delegate

    def reverse_url(self, name: str, *args: Any, **kwargs: Any) -> str:
        return self.router.reverse_url(name, *args, **kwargs)

    def application_urls(self) -> list[tuple]:
        return [('', FileMappingRouter(importlib.import_module(f'{self.app_module}.pages')))]

    def application_404_handler(self, request: HTTPServerRequest) -> tuple:
        return ErrorHandler, {'status_code': 404}

    def application_config(self) -> DefaultConfig:
        return FrontikApplication.DefaultConfig()

    def application_version_xml(self) -> list[etree.Element]:
        version = etree.Element('version')
        version.text = 'unknown'
        return [version]

    def application_version(self) -> str|None:
        return None

    @staticmethod
    def next_request_id() -> str:
        FrontikApplication.request_id = generate_uniq_timestamp_request_id()
        return FrontikApplication.request_id

    def get_current_status(self) -> dict[str, str]:
        if self.init_workers_count_down.value > 0:
            raise HTTPError(
                500, f'some workers are not started ' f'init_workers_count_down={self.init_workers_count_down.value}'
            )

        cur_uptime = time.time() - self.start_time
        if cur_uptime < 60:
            uptime_value = '{:.2f} seconds'.format(cur_uptime)
        elif cur_uptime < 3600:
            uptime_value = '{:.2f} minutes'.format(cur_uptime / 60)
        else:
            uptime_value = '{:.2f} hours and {:.2f} minutes'.format(cur_uptime / 3600, (cur_uptime % 3600) / 60)

        return {
            'uptime': uptime_value,
            'datacenter': http_client_options.datacenter,
        }

    def log_request(self, handler):
        if not options.log_json:
            super().log_request(handler)
            return

        request_time = int(1000.0 * handler.request.request_time())
        extra = {
            'ip': handler.request.remote_ip,
            'rid': request_context.get_request_id(),
            'status': handler.get_status(),
            'time': request_time,
            'method': handler.request.method,
            'uri': handler.request.uri,
        }

        handler_name = request_context.get_handler_name()
        if handler_name:
            extra['controller'] = handler_name

        JSON_REQUESTS_LOGGER.info('', extra={CUSTOM_JSON_EXTRA: extra})

    def get_kafka_producer(self, producer_name: str) -> 'Optional[AIOKafkaProducer]':  # pragma: no cover
        pass


def get_frontik_and_apps_versions(application: FrontikApplication) -> etree.Element:
    versions = etree.Element('versions')

    etree.SubElement(versions, 'frontik').text = frontik_version
    etree.SubElement(versions, 'tornado').text = tornado.version
    etree.SubElement(versions, 'lxml.etree.LXML').text = '.'.join(str(x) for x in etree.LXML_VERSION)
    etree.SubElement(versions, 'lxml.etree.LIBXML').text = '.'.join(str(x) for x in etree.LIBXML_VERSION)
    etree.SubElement(versions, 'lxml.etree.LIBXSLT').text = '.'.join(str(x) for x in etree.LIBXSLT_VERSION)
    etree.SubElement(versions, 'aiohttp').text = aiohttp.__version__
    etree.SubElement(versions, 'python').text = sys.version.replace('\n', '')
    etree.SubElement(versions, 'event_loop').text = str(type(asyncio.get_event_loop())).split("'")[1]
    etree.SubElement(versions, 'application', name=options.app).extend(application.application_version_xml())

    return versions
