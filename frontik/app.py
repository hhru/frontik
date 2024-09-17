import asyncio
import importlib
import logging
import multiprocessing
import os
import time
from ctypes import c_bool, c_int
from typing import Any, Optional, Union

from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, HTTPException
from http_client import AIOHttpClientWrapper, HttpClientFactory
from http_client import options as http_client_options
from http_client.balancing import RequestBalancerBuilder
from lxml import etree
from tornado import httputil

import frontik.producers.json_producer
import frontik.producers.xml_producer
from frontik import app_integrations, media_types
from frontik.app_integrations.statsd import StatsDClient, StatsDClientStub, create_statsd_client
from frontik.debug import get_frontik_and_apps_versions
from frontik.handler import PageHandler, get_current_handler
from frontik.handler_asgi import serve_tornado_request
from frontik.handler_return_values import ReturnedValueHandlers, get_default_returned_value_handlers
from frontik.options import options
from frontik.process import WorkerState
from frontik.routing import (
    import_all_pages,
    method_not_allowed_router,
    not_found_router,
    regex_router,
    router,
    routers,
)
from frontik.service_discovery import MasterServiceDiscovery, ServiceDiscovery, WorkerServiceDiscovery

app_logger = logging.getLogger('app_logger')
_server_tasks = set()


class FrontikAsgiApp(FastAPI):
    def __init__(self) -> None:
        super().__init__()
        self.router = router
        self.http_client_factory = None

        if options.openapi_enabled:
            self.setup()

        for _router in routers:
            self.include_router(_router)


def anyio_noop(*_args: Any, **_kwargs: Any) -> None:
    raise RuntimeError(f'trying to use non async {_args[0]}')


class FrontikApplication:
    request_id = ''

    class DefaultConfig:
        pass

    def __init__(self, app_module_name: Optional[str] = None) -> None:
        self.start_time = time.time()
        self.patch_anyio()

        self.app_module_name: str = app_module_name or self.__class__.__module__
        app_module = importlib.import_module(self.app_module_name)
        self.app_root = os.path.dirname(str(app_module.__file__))
        if options.service_name is None:
            options.service_name = self.app_module_name.rsplit('.', 1)[-1]
        self.app_name = options.service_name

        self.config = self.application_config()

        self.xml = frontik.producers.xml_producer.XMLProducerFactory(self)
        self.json = frontik.producers.json_producer.JsonProducerFactory(self)

        self.available_integrations: list[app_integrations.Integration] = []
        self.http_client_factory: HttpClientFactory

        self.statsd_client: Union[StatsDClient, StatsDClientStub] = create_statsd_client(options, self)

        init_workers_count_down = multiprocessing.Value(c_int, options.workers)
        master_done = multiprocessing.Value(c_bool, False)
        count_down_lock = multiprocessing.Lock()
        self.worker_state = WorkerState(init_workers_count_down, master_done, count_down_lock)  # type: ignore
        self.returned_value_handlers: ReturnedValueHandlers = get_default_returned_value_handlers()

        import_all_pages(self.app_module_name)
        assert len(not_found_router.routes) < 2
        assert len(method_not_allowed_router.routes) < 2

        self.settings: dict = {}

        self.asgi_app = FrontikAsgiApp()
        self.service_discovery: ServiceDiscovery

    def patch_anyio(self) -> None:
        """
        We have problems with anyio running sync dependencies in threadpool, so sync deps are prohibited
        """
        try:
            import anyio

            anyio.to_thread.run_sync = anyio_noop  # type: ignore
        except ImportError:
            pass

    def __call__(self, tornado_request: httputil.HTTPServerRequest) -> None:
        # for make it more asgi, reimplement tornado.http1connection._server_request_loop and ._read_message
        task = asyncio.create_task(serve_tornado_request(self, self.asgi_app, tornado_request))
        _server_tasks.add(task)
        task.add_done_callback(_server_tasks.discard)

    def make_service_discovery(self) -> ServiceDiscovery:
        if self.worker_state.is_master and options.consul_enabled:
            return MasterServiceDiscovery(self.statsd_client, self.app_name)
        else:
            return WorkerServiceDiscovery(self.worker_state.initial_shared_data)

    async def install_integrations(self) -> None:
        self.available_integrations, integration_futures = app_integrations.load_integrations(self)
        await asyncio.gather(*[future for future in integration_futures if future])

        self.service_discovery = self.make_service_discovery()
        self.http_client_factory = self.make_http_client_factory()
        self.asgi_app.http_client_factory = self.http_client_factory

    async def init(self) -> None:
        await self.install_integrations()

        if self.worker_state.is_master:
            self.worker_state.master_done.value = True

    def make_http_client_factory(self) -> HttpClientFactory:
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

        kafka_producer = (
            self.get_kafka_producer(kafka_cluster) if send_metrics_to_kafka and kafka_cluster is not None else None
        )

        request_balancer_builder = RequestBalancerBuilder(
            upstreams=self.service_discovery.get_upstreams_unsafe(),
            statsd_client=self.statsd_client,
            kafka_producer=kafka_producer,
        )
        return HttpClientFactory(self.app_name, AIOHttpClientWrapper(), request_balancer_builder)

    def application_config(self) -> DefaultConfig:
        return FrontikApplication.DefaultConfig()

    def application_version_xml(self) -> list[etree.Element]:
        version = etree.Element('version')
        version.text = 'unknown'
        return [version]

    def application_version(self) -> str:
        return 'unknown'

    def get_current_status(self) -> dict[str, str]:
        not_started_workers = self.worker_state.init_workers_count_down.value
        master_done = self.worker_state.master_done.value
        if not_started_workers > 0 or not master_done:
            raise HTTPException(
                500,
                f'some workers are not started not_started_workers={not_started_workers}, master_done={master_done}',
            )

        cur_uptime = time.time() - self.start_time
        if cur_uptime < 60:
            uptime_value = f'{cur_uptime:.2f} seconds'
        elif cur_uptime < 3600:
            uptime_value = f'{cur_uptime / 60:.2f} minutes'
        else:
            uptime_value = f'{cur_uptime / 3600:.2f} hours and {(cur_uptime % 3600) / 60:.2f} minutes'

        return {'uptime': uptime_value, 'datacenter': http_client_options.datacenter}

    def get_kafka_producer(self, producer_name: str) -> Optional[AIOKafkaProducer]:  # pragma: no cover
        pass

    def log_request(self, tornado_handler: PageHandler) -> None:
        pass


@regex_router.get('/version', cls=PageHandler)
async def get_version(handler: PageHandler = get_current_handler()) -> None:
    handler.set_header('Content-Type', 'text/xml')
    handler.finish(
        etree.tostring(get_frontik_and_apps_versions(handler.application), encoding='utf-8', xml_declaration=True),
    )


@regex_router.get('/status', cls=PageHandler)
async def get_status(handler: PageHandler = get_current_handler()) -> None:
    handler.set_header('Content-Type', media_types.APPLICATION_JSON)
    handler.finish(handler.application.get_current_status())
