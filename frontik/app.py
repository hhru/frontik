import asyncio
import inspect
import logging
import multiprocessing
import os
import sys
import time
from ctypes import c_bool, c_int
from typing import TYPE_CHECKING, Any, Optional, Union

import aiohttp
import tornado
from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import ORJSONResponse
from http_client import HttpClient, HttpClientFactory
from http_client import options as http_client_options
from http_client.balancing import RequestBalancerBuilder
from http_client.request_response import FailFastError
from lxml import etree
from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Receive, Scope, Send
from tornado import httputil

from frontik import app_integrations
from frontik.app_integrations.scylla import ScyllaCluster
from frontik.app_integrations.statsd import create_statsd_client
from frontik.balancing_client import (
    OutOfRequestTime,
    fail_fast_error_handler,
    out_of_request_time_error_handler,
    set_extra_client_params,
)
from frontik.dependencies import set_app
from frontik.dev_route_manager import DevRouteManager
from frontik.handler_asgi import default_exception_handler
from frontik.http_status import CLIENT_CLOSED_REQUEST
from frontik.options import DEV_MODE_ON_DEMAND_ROUTING, options
from frontik.process import WorkerState
from frontik.routing import (
    import_all_pages,
    method_not_allowed_router,
    not_found_router,
    preflight_router,
    router,
    routers,
)
from frontik.service_discovery import MasterServiceDiscovery, ServiceDiscovery, WorkerServiceDiscovery
from frontik.tornado_connection_handler import TornadoConnectionHandler
from frontik.util import Sentinel
from frontik.util.fastapi import make_plain_response
from frontik.version import version as frontik_version

if TYPE_CHECKING:
    from pystatsd import StatsDClientABC

app_logger = logging.getLogger('app_logger')
_DEFAULT_ARG = Sentinel()


class FrontikApplication(FastAPI, httputil.HTTPServerConnectionDelegate):
    class DefaultConfig:
        pass

    def __init__(self, app_module_name: Union[str, Sentinel, None] = _DEFAULT_ARG) -> None:
        self.start_time = time.time()
        super().__init__()
        self.patch_anyio()

        self.app_module_name: str = app_module_name if isinstance(app_module_name, str) else self.__class__.__module__
        self.app_root = os.path.dirname(inspect.getfile(self.__class__))
        if options.service_name is None:
            options.service_name = self.app_module_name.rsplit('.', 1)[-1]
        self.app_name = options.service_name
        self.route_manager: Union[DevRouteManager, None] = None

        self.config: Any = self.application_config()

        self.available_integrations: list[app_integrations.Integration] = []

        self.statsd_client: StatsDClientABC = create_statsd_client(options, self)
        self.service_discovery: ServiceDiscovery
        self._http_client_factory: HttpClientFactory
        self.http_client: HttpClient

        init_workers_count_down = multiprocessing.Value(c_int, options.workers)
        master_done = multiprocessing.Value(c_bool, False)
        count_down_lock = multiprocessing.Lock()
        self.worker_state = WorkerState(init_workers_count_down, master_done, count_down_lock)  # type: ignore

        if app_module_name is not None:
            if options.dev_mode == DEV_MODE_ON_DEMAND_ROUTING:
                self.route_manager = DevRouteManager()
                self.route_manager.import_all_pages(self.app_module_name)
                self.include_router(self.route_manager.fake_dev_router, prefix='/fake')
            else:
                import_all_pages(self.app_module_name)

        self.router = router

        for _router in routers:
            if _router is not router:
                self.include_router(_router)

        if options.openapi_enabled:
            self.setup()

        self.add_middleware(FrontikMiddleware)
        self.add_exception_handler(FailFastError, fail_fast_error_handler)  # type: ignore[arg-type]
        self.add_exception_handler(ClientDisconnect, client_disconnect_error_handler)  # type: ignore[arg-type]
        self.add_exception_handler(OutOfRequestTime, out_of_request_time_error_handler)  # type: ignore[arg-type]
        self.add_exception_handler(Exception, default_exception_handler)

    def patch_anyio(self) -> None:
        """
        We have problems with anyio running sync dependencies in threadpool, so sync deps are prohibited
        """
        try:
            import anyio

            anyio.to_thread.run_sync = anyio_noop  # type: ignore
        except ImportError:
            pass

    def make_service_discovery(self) -> ServiceDiscovery:
        if self.worker_state.is_master and options.consul_enabled:
            return MasterServiceDiscovery(self.statsd_client, self.app_name)
        else:
            return WorkerServiceDiscovery(self.worker_state.initial_shared_data)

    async def install_integrations(self) -> None:
        set_app(self)

        self.service_discovery = self.make_service_discovery()
        self.available_integrations, integration_futures = app_integrations.load_integrations(self)
        await asyncio.gather(*[future for future in integration_futures if future])

        self._http_client_factory = self.make_http_client_factory()
        self.http_client = self._http_client_factory.get_http_client()

    async def init(self) -> None:
        await self.install_integrations()

        if self.worker_state.is_master:
            self.worker_state.master_done.value = True

    async def deinit(self) -> None:
        if self.http_client is not None:
            await asyncio.wait_for(self.http_client.http_client_impl.client_session.close(), timeout=1.0)

        for integration in self.available_integrations:
            integration.deinitialize_app(self)

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
            upstream_getter=self.service_discovery.get_upstream,
            statsd_client=self.statsd_client,
            kafka_producer=kafka_producer,
        )
        return HttpClientFactory(self.app_name, request_balancer_builder)

    def application_config(self) -> DefaultConfig:
        return FrontikApplication.DefaultConfig()

    def application_version_xml(self) -> list[etree.Element]:
        version = etree.Element('version')
        version.text = self.application_version()
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

        return {
            'uptime': uptime_value,
            'datacenter': http_client_options.datacenter,
            'app_version': self.application_version(),
        }

    def get_frontik_and_apps_versions(self) -> etree.Element:
        versions = etree.Element('versions')

        etree.SubElement(versions, 'frontik').text = frontik_version
        etree.SubElement(versions, 'tornado').text = tornado.version
        etree.SubElement(versions, 'lxml.etree.LXML').text = '.'.join(str(x) for x in etree.LXML_VERSION)
        etree.SubElement(versions, 'lxml.etree.LIBXML').text = '.'.join(str(x) for x in etree.LIBXML_VERSION)
        etree.SubElement(versions, 'lxml.etree.LIBXSLT').text = '.'.join(str(x) for x in etree.LIBXSLT_VERSION)
        etree.SubElement(versions, 'aiohttp').text = aiohttp.__version__
        etree.SubElement(versions, 'python').text = sys.version.replace('\n', '')
        etree.SubElement(versions, 'event_loop').text = str(type(asyncio.get_event_loop())).split("'")[1]
        etree.SubElement(versions, 'application', name=self.app_module_name).extend(self.application_version_xml())

        return versions

    def get_kafka_producer(self, producer_name: str) -> Optional[AIOKafkaProducer]:  # pragma: no cover
        pass

    def get_scylla_cluster(self, cluster_name: str) -> Optional[ScyllaCluster]:
        pass

    def start_request(
        self,
        server_conn: object,
        request_conn: httputil.HTTPConnection,
    ) -> TornadoConnectionHandler:
        return TornadoConnectionHandler(self, request_conn)


def anyio_noop(*_args: Any, **_kwargs: Any) -> None:
    raise RuntimeError(f'trying to use non async {_args[0]}')


@router.get('/version')
async def get_version(request: Request) -> Response:
    data = etree.tostring(request.app.get_frontik_and_apps_versions(), encoding='utf-8', xml_declaration=True)
    return Response(content=data, media_type='text/xml')


@router.get('/status')
async def get_status(request: Request) -> ORJSONResponse:
    return ORJSONResponse(request.app.get_current_status())


class FrontikMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        with set_extra_client_params(scope):
            await self.app(scope, receive, send)


@not_found_router.get('__not_found')
async def default_404() -> Response:
    return Response(status_code=404)


@method_not_allowed_router.get('__method_not_allowed')
async def default_405(request: Request) -> Response:
    return Response(status_code=405, headers={'Allow': ', '.join(request.scope['allowed_methods'])})


@preflight_router.options('__preflight_options')
async def default_preflight_options() -> Response:
    # CORS should be handled by CORSMiddleware in application code
    return Response(status_code=204)


async def client_disconnect_error_handler(server_request: Request, exc: ClientDisconnect) -> Response:
    return make_plain_response(CLIENT_CLOSED_REQUEST)
