import asyncio
import importlib
import logging
import multiprocessing
import sys
import time
import traceback
from collections.abc import Callable
from ctypes import c_bool, c_int
from functools import partial
from threading import Lock
from typing import Any, Optional, Union
import json
import inspect
import re

from aiokafka import AIOKafkaProducer
from http_client import AIOHttpClientWrapper, HttpClientFactory
from http_client import options as http_client_options
from http_client.balancing import RequestBalancerBuilder, Upstream
from lxml import etree
from tornado import httputil
from tornado.httputil import HTTPServerRequest
from tornado.web import Application, HTTPError, RequestHandler

import frontik.producers.json_producer
import frontik.producers.xml_producer
from frontik import integrations, media_types, request_context
from frontik.debug import DebugTransform, get_frontik_and_apps_versions
from frontik.handler import PageHandler, FinishPageSignal, RedirectPageSignal, build_error_data
from frontik.handler_return_values import ReturnedValueHandlers, get_default_returned_value_handlers
from frontik.integrations.statsd import StatsDClient, StatsDClientStub, create_statsd_client
from frontik.loggers import CUSTOM_JSON_EXTRA, JSON_REQUESTS_LOGGER
from frontik.options import options
from frontik.process import WorkerState
from frontik.routing import routers, normal_routes, regex_mapping, FrontikRouter, FrontikRegexRouter
from frontik.service_discovery import UpstreamManager
from frontik.util import check_request_id, generate_uniq_timestamp_request_id
from fastapi import FastAPI, APIRouter, Request
from fastapi.routing import APIRoute
import pkgutil
from http_client import HttpClient
from starlette.middleware.base import Response
from fastapi import Depends
import os
from inspect import ismodule
from starlette.datastructures import MutableHeaders
from frontik.json_builder import json_decode
from frontik.handler import get_current_handler

app_logger = logging.getLogger('app_logger')

_core_router = FrontikRouter()
router = FrontikRouter()
regex_router = FrontikRegexRouter()
routers.extend((_core_router, router, regex_router))


def setup_page_handler(request: Request, cls: type(PageHandler)):
    # create legacy PageHandler and put to request
    handler = cls(
        request.app.frontik_app,
        request.query_params,
        request.cookies,
        request.headers,
        request.state.body_bytes,
        request.state.start_time,
        request.url.path,
        request.state.path_params,
        request.client.host,
        request.method,
    )

    request.state.handler = handler
    return handler


def _data_to_chunk(data, headers) -> bytes:
    if isinstance(data, str):
        chunk = data.encode("utf-8")
    elif isinstance(data, dict):
        chunk = json.dumps(data).replace("</", "<\\/")
        chunk = chunk.encode("utf-8")
        headers["Content-Type"] = "application/json; charset=UTF-8"
    elif isinstance(data, bytes):
        chunk = data
    else:
        raise RuntimeError('unexpected type of chunk')
    return chunk


async def core_middleware(request: Request, call_next):
    request.state.start_time = time.time()
    request.state.body_bytes = await request.body()

    request_id = request.headers.get('X-Request-Id') or FrontikApplication.next_request_id()
    if options.validate_request_id:
        check_request_id(request_id)

    with request_context.request_context(request, request_id):
        route = normal_routes.get((request.url.path, request.method))
        if route is None:
            return await call_next(request)  # если в нормальных не нашли, пусть фолбэчнется на регекс роутер

        page_cls = route[1]  # from normal router
        request.state.path_params = {}
        setup_page_handler(request, page_cls)

        _call_next = route[0].get_route_handler()
        response = await process_request(request, _call_next)
        return response


async def regex_router_fallback(request: Request, _):
    for pattern, route, cls in regex_mapping:
        route: APIRoute
        match = pattern.match(request.url.path)
        if match and next(iter(route.methods), None) == request.method:
            request.state.path_params = match.groupdict()
            setup_page_handler(request, cls)
            call_next = route.get_route_handler()
            response = await process_request(request, call_next)
            return response

    rid = request_context.get_request_id()
    status, headers, content = build_error_data(rid, 404, 'Not Found')
    return Response(status_code=status, headers=headers, content=content)


@_core_router.get('/version', cls=PageHandler)
async def get_version(self=get_current_handler):
    self.set_header('Content-Type', 'text/xml')
    self.finish(
        etree.tostring(get_frontik_and_apps_versions(self.application), encoding='utf-8', xml_declaration=True),
    )


@_core_router.get('/status', cls=PageHandler)
async def get_status(self=get_current_handler):
    self.set_header('Content-Type', media_types.APPLICATION_JSON)
    self.finish(self.application.get_current_status())


class PydevdHandler(RequestHandler):
    def get(self):
        if hasattr(sys, 'gettrace') and sys.gettrace() is not None:
            self.already_tracing_page()
            return

        try:
            debugger_ip = self.get_query_argument('debugger_ip', self.request.remote_ip)
            debugger_port = self.get_query_argument('debugger_port', '32223')
            self.settrace(debugger_ip, int(debugger_port))
            self.trace_page(debugger_ip, debugger_port)

        except BaseException:
            self.error_page()

    def settrace(self, debugger_ip: Optional[str], debugger_port: int) -> None:
        import pydevd

        pydevd.settrace(debugger_ip, port=debugger_port, stdoutToServer=True, stderrToServer=True, suspend=False)

    def trace_page(self, ip: Optional[str], port: str) -> None:
        self.set_header('Content-Type', media_types.TEXT_PLAIN)
        self.finish(f'Connected to debug server at {ip}:{port}')

    def already_tracing_page(self) -> None:
        self.set_header('Content-Type', media_types.TEXT_PLAIN)
        self.finish('App is already in tracing mode, try to restart service')

    def error_page(self) -> None:
        self.set_header('Content-Type', media_types.TEXT_PLAIN)
        self.finish(traceback.format_exc())


class FrontikApplication:
    request_id = ''

    class DefaultConfig:
        pass

    def __init__(self, app_root: str, **settings: Any) -> None:
        self.start_time = time.time()

        self.app = settings.get('app')
        self.app_module = settings.get('app_module')
        self.app_root = app_root

        self.config = self.application_config()

        self.xml = frontik.producers.xml_producer.XMLProducerFactory(self)
        self.json = frontik.producers.json_producer.JsonProducerFactory(self)

        self.available_integrations: list[integrations.Integration] = []
        self.tornado_http_client: Optional[AIOHttpClientWrapper] = None
        self.http_client_factory: HttpClientFactory

        self.statsd_client: Union[StatsDClient, StatsDClientStub] = create_statsd_client(options, self)

        init_workers_count_down = multiprocessing.Value(c_int, options.workers)
        master_done = multiprocessing.Value(c_bool, False)
        count_down_lock = multiprocessing.Lock()
        self.worker_state = WorkerState(init_workers_count_down, master_done, count_down_lock)  # type: ignore

        self.returned_value_handlers: ReturnedValueHandlers = get_default_returned_value_handlers()

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
        )

        self.upstream_manager.send_updates()  # initial full state sending

    async def init(self) -> None:
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
        self.http_client_factory = HttpClientFactory(self.app, self.tornado_http_client, request_balancer_builder)
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

    @staticmethod
    def next_request_id() -> str:
        FrontikApplication.request_id = generate_uniq_timestamp_request_id()
        return FrontikApplication.request_id

    def get_current_status(self) -> dict[str, str]:
        not_started_workers = self.worker_state.init_workers_count_down.value
        master_done = self.worker_state.master_done.value
        if not_started_workers > 0 or not master_done:
            raise HTTPError(
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

    def log_request(self, handler, request: Request):
        request_time = int(1000.0 * (time.time() - handler.request_start_time))
        extra = {
            'ip': request.client.host,
            'rid': request_context.get_request_id(),
            'status': handler.get_status(),
            'time': request_time,
            'method': request.method,
            'uri': str(request.url),
        }

        handler_name = request_context.get_handler_name()
        if handler_name:
            extra['controller'] = handler_name

        JSON_REQUESTS_LOGGER.info('', extra={CUSTOM_JSON_EXTRA: extra})

    def get_kafka_producer(self, producer_name: str) -> Optional[AIOKafkaProducer]:  # pragma: no cover
        pass


async def process_request(request, call_next):
    handler = request.state.handler
    status = 200
    headers = {}
    content = None

    try:
        request_context.set_handler(handler)

        handler.prepare()
        handler.stages_logger.commit_stage('prepare')
        _response = await call_next(request)

        handler._handler_finished_notification()
        await handler.finish_group.get_gathering_future()
        await handler.finish_group.get_finish_future()
        handler.stages_logger.commit_stage('page')

        render_result = await handler._postprocess()
        handler.stages_logger.commit_stage('postprocess')

        headers = handler.resp_headers
        status = handler.get_status()

        debug_transform = DebugTransform(request.app.frontik_app, request)
        if debug_transform.is_enabled():
            chunk = _data_to_chunk(render_result, headers)
            status, headers, render_result = debug_transform.transform_chunk(status, headers, chunk)

        content = render_result

    except FinishPageSignal as finish_ex:
        handler._handler_finished_notification()
        headers = handler.resp_headers
        chunk = _data_to_chunk(finish_ex.data, headers)
        status = handler.get_status()
        content = chunk

    except RedirectPageSignal as redirect_ex:
        handler._handler_finished_notification()
        headers = handler.resp_headers
        url = redirect_ex.url
        status = redirect_ex.status
        headers["Location"] = url.encode('utf-8')

    except Exception as ex:
        try:
            status, headers, content = await handler._handle_request_exception(ex)
        except Exception as exc:
            app_logger.exception(f'request processing has failed')
            status, headers, content = build_error_data(handler.request_id)

    finally:
        handler.cleanup()

    if status in (204, 304) or (100 <= status < 200):
        for h in ('Content-Encoding', 'Content-Language', 'Content-Type'):
            if h in headers:
                headers.pop(h)
        content = None

    response = Response(status_code=status, headers=headers, content=content)

    for key, values in handler.resp_cookies.items():
        response.set_cookie(key, **values)

    handler.finish_group.abort()
    request.app.frontik_app.log_request(handler, request)
    handler.on_finish(status)

    return response
