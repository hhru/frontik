import asyncio
import importlib
import logging
import multiprocessing
import os
import time
from collections.abc import Callable
from ctypes import c_bool, c_int
from threading import Lock
from typing import Optional, Union

from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, HTTPException
from http_client import AIOHttpClientWrapper, HttpClientFactory
from http_client import options as http_client_options
from http_client.balancing import RequestBalancerBuilder, Upstream
from lxml import etree

import frontik.producers.json_producer
import frontik.producers.xml_producer
from frontik import integrations, media_types
from frontik.debug import get_frontik_and_apps_versions
from frontik.handler import PageHandler, get_current_handler
from frontik.integrations.statsd import StatsDClient, StatsDClientStub, create_statsd_client
from frontik.options import options
from frontik.process import WorkerState
from frontik.routing import router
from frontik.service_discovery import UpstreamManager

app_logger = logging.getLogger('app_logger')


@router.get('/version', cls=PageHandler)
async def get_version(handler: PageHandler = get_current_handler()) -> None:
    handler.set_header('Content-Type', 'text/xml')
    handler.finish(
        etree.tostring(get_frontik_and_apps_versions(handler.application), encoding='utf-8', xml_declaration=True),
    )


@router.get('/status', cls=PageHandler)
async def get_status(handler: PageHandler = get_current_handler()) -> None:
    handler.set_header('Content-Type', media_types.APPLICATION_JSON)
    handler.finish(handler.application.get_current_status())


class FrontikApplication:
    request_id = ''

    class DefaultConfig:
        pass

    def __init__(self, app_module_name: Optional[str] = None) -> None:
        self.start_time = time.time()

        self.fastapi_app = FastAPI()

        self.app_module_name: Optional[str] = app_module_name
        if app_module_name is None:
            app_module = importlib.import_module(self.__class__.__module__)
        else:
            app_module = importlib.import_module(app_module_name)
        self.app_root = os.path.dirname(str(app_module.__file__))
        self.app_name = app_module.__name__

        self.config = self.application_config()

        self.xml = frontik.producers.xml_producer.XMLProducerFactory(self)
        self.json = frontik.producers.json_producer.JsonProducerFactory(self)

        self.available_integrations: list[integrations.Integration] = []
        self.http_client: Optional[AIOHttpClientWrapper] = None
        self.http_client_factory: HttpClientFactory

        self.statsd_client: Union[StatsDClient, StatsDClientStub] = create_statsd_client(options, self)

        # init_workers_count_down = multiprocessing.Value(c_int, options.workers)
        # master_done = multiprocessing.Value(c_bool, False)
        # count_down_lock = multiprocessing.Lock()
        # self.worker_state = WorkerState(init_workers_count_down, master_done, count_down_lock)  # type: ignore

    def create_upstream_manager(
        self,
        upstreams: dict[str, Upstream],
        upstreams_lock: Optional[Lock],
        send_to_all_workers: Optional[Callable],
        with_consul: bool,
    ) -> None:
        self.upstream_manager = UpstreamManager(
            upstreams,
            self.statsd_client,
            upstreams_lock,
            send_to_all_workers,
            with_consul,
            self.app_name,
        )

        self.upstream_manager.send_updates()  # initial full state sending

    async def init(self) -> None:
        self.available_integrations, integration_futures = integrations.load_integrations(self)
        await asyncio.gather(*[future for future in integration_futures if future])

        self.http_client = AIOHttpClientWrapper()

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

        with_consul = self.worker_state.single_worker_mode and options.consul_enabled
        self.create_upstream_manager({}, None, None, with_consul)
        self.upstream_manager.register_service()

        request_balancer_builder = RequestBalancerBuilder(
            self.upstream_manager.get_upstreams(),
            statsd_client=self.statsd_client,
            kafka_producer=kafka_producer,
        )
        self.http_client_factory = HttpClientFactory(self.app_name, self.http_client, request_balancer_builder)
        if self.worker_state.single_worker_mode:
            self.worker_state.master_done.value = True

    def application_config(self) -> DefaultConfig:
        return FrontikApplication.DefaultConfig()

    def application_version_xml(self) -> list[etree.Element]:
        version = etree.Element('version')
        version.text = 'unknown'
        return [version]

    def application_version(self) -> Optional[str]:
        return None

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
