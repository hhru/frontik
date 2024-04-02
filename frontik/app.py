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
from frontik.handler import ErrorHandler, PageHandler, MyFinishError, MyRedirectError
from frontik.handler_return_values import ReturnedValueHandlers, get_default_returned_value_handlers
from frontik.integrations.statsd import StatsDClient, StatsDClientStub, create_statsd_client
from frontik.loggers import CUSTOM_JSON_EXTRA, JSON_REQUESTS_LOGGER
from frontik.options import options
from frontik.process import WorkerState
from frontik.routing import FileMappingRouter, FrontikRouter
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

app_logger = logging.getLogger('app_logger')

routers = []
mega_routes = {}
regex_mapping = []


def import_submodules(package):
    package = importlib.import_module(package)
    for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = package.__name__ + '.' + name
        try:
            importlib.import_module(full_name)
        except ModuleNotFoundError:
            continue
        except Exception as ex:
            app_logger.error('failed on import page %s %s', full_name, ex)
            continue
        if is_pkg:
            import_submodules(full_name)


def fill_router(frontik_app):
    package_name = f'{frontik_app.app_module}.pages'
    import_submodules(package_name)


class CustomRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        routers.append(self)
        self._cls = None
        self._path = None

    def get(self, path: str, **kwargs) -> Callable:
        self._cls, self._path = kwargs.pop('cls'), path
        return super().get(path, **kwargs)

    def post(self, path: str, **kwargs) -> Callable:
        self._cls, self._path = kwargs.pop('cls'), path
        return super().post(path, **kwargs)

    def put(self, path: str, **kwargs) -> Callable:
        self._cls, self._path = kwargs.pop('cls'), path
        return super().put(path, **kwargs)

    def delete(self, path: str, **kwargs) -> Callable:
        self._cls, self._path = kwargs.pop('cls'), path
        return super().delete(path, **kwargs)

    def add_api_route(self, *args, **kwargs):
        super().add_api_route(*args, **kwargs)
        mega_routes[self._path] = (self.routes[-1], self._cls)  # это нужно для того чтобы хендлер билдить
        self._cls, self._path = None, None


def create_handler(request: Request, cls: type(PageHandler)):
    print('delau frontik handler')
    new_handler = cls(
        request.app.frontik_app,
        request.query_params,
        request.cookies,
        request.headers,
        request.state.body_bytes,
        request.state.start_time,
        request.url.path
    )

    request.state.handler = new_handler
    return new_handler


async def _self_getter1(request: Request):
    return request.state.handler

class CustomRouter2(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        routers.append(self)
        self._cls = None
        self._path = None

    def get(self, path: str, **kwargs) -> Callable:
        self._cls, self._path = kwargs.pop('cls'), path
        return super().get(path, **kwargs)

    def post(self, path: str, **kwargs) -> Callable:
        self._cls, self._path = kwargs.pop('cls'), path
        return super().post(path, **kwargs)

    def put(self, path: str, **kwargs) -> Callable:
        self._cls, self._path = kwargs.pop('cls'), path
        return super().put(path, **kwargs)

    def delete(self, path: str, **kwargs) -> Callable:
        self._cls, self._path = kwargs.pop('cls'), path
        return super().delete(path, **kwargs)

    def add_api_route(self, *args, **kwargs):
        super().add_api_route(*args, **kwargs)

        regex_mapping.append((
            re.compile(self._path),
            self.routes[-1],
            self._cls
        ))

        self._cls, self._path = None, None

self_getter = Depends(_self_getter1)
core_router = CustomRouter()
router = CustomRouter()
regex_router = CustomRouter2()
routers.extend((core_router, router, regex_router))


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


async def core_middle_ware(request: Request, call_next):
    print(f'-----core----midlware---')
    request.state.start_time = time.time()
    request.state.body_bytes = await request.body()  # сразу все нахуй выгружаем даже если там килотонна

    if hasattr(request.state, 'cls'):
        page_cls = request.state.cls
    else:
        page_cls = mega_routes.get(request.url.path)[1]
    handler: PageHandler = create_handler(request, page_cls)

    request_id = request.headers.get('X-Request-Id') or FrontikApplication.next_request_id()
    if options.validate_request_id:
        check_request_id(request_id)

    status = 200
    headers = {}
    content = None

    with request_context.request_context(request, request_id, handler):
        try:
            handler.stages_logger.commit_stage('prepare')
            _response = await call_next(request)

            handler._handler_finished_notification()
            await handler.finish_group.get_gathering_future()
            await handler.finish_group.get_finish_future()
            handler.stages_logger.commit_stage('page')

            render_result = await handler._postprocess()
            handler.stages_logger.commit_stage('postprocess')

            final_headers = handler.resp_headers

            debug_transform = DebugTransform(request.app.frontik_app, request)
            if debug_transform.is_enabled():
                chunk = _data_to_chunk(render_result, final_headers)
                handler._status, final_headers, render_result = debug_transform.transform_first_chunk(handler._status, final_headers, chunk)

            if render_result is None:
                raise RuntimeError('my poka ne gotovy k takomu3')

            status = handler._status
            content = render_result
            headers = final_headers

        except MyFinishError as finish_ex:
            handler._handler_finished_notification()
            chunk = _data_to_chunk(finish_ex.data, headers)
            status = handler._status
            content = chunk

        except MyRedirectError as redirect_ex:
            handler._handler_finished_notification()
            url = redirect_ex.url
            status = redirect_ex.status
            headers["Location"] = url.encode('utf-8')

        except Exception as ex:
            handler._handle_request_exception(ex)

        finally:
            handler.cleanup()

        if status in (204, 304) or (100 <= status < 200):
            headers1 = ["Content-Encoding", "Content-Language", "Content-Type"]
            for h in headers1:
                headers.pop(h)
            content = None

        response = Response(status_code=status, headers=headers, content=content)

        for key, values in handler.resp_cookies.items():
            response.set_cookie(key, **values)

        # on_conn_close   бля эта хуйня из эксепшена когда соединение разорвалось
        handler.finish_group.abort()
        request.app.frontik_app.log_request(handler, request)
        handler.on_finish()

        return response


def build_path() -> str:
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)
    page_file_path = calframe[1].filename
    idx = page_file_path.find('/pages')
    if idx == -1:
        raise RuntimeError('cant generate url path')

    return page_file_path[idx + 6:-3]


class RequestCancelledMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        print('-----cancel----midlware---')
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Let's make a shared queue for the request messages
        queue = asyncio.Queue()

        async def message_poller(sentinel, handler_task):
            nonlocal queue
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    handler_task.cancel()
                    return sentinel  # Break the loop

                # Puts the message in the queue
                await queue.put(message)

        sentinel = object()
        handler_task = asyncio.create_task(self.app(scope, queue.get, send))
        poller_task = asyncio.create_task(message_poller(sentinel, handler_task))
        poller_task.done()

        try:
            return await handler_task
        except asyncio.CancelledError:
            pass
            # print("Cancelling request due to disconnect")


@core_router.get('/version', cls=PageHandler)
async def get_version(self=self_getter):
    self.set_header('Content-Type', 'text/xml')
    self.finish(
        etree.tostring(get_frontik_and_apps_versions(self.application), encoding='utf-8', xml_declaration=True),
    )


@core_router.get('/status', cls=PageHandler)
async def get_status(self=self_getter):
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


# class FrontikApplication(Application):
from tornado.web import Application

class FrontikApplication:
    request_id = ''

    class DefaultConfig:
        pass

    def __init__(self, app_root: str, **settings: Any) -> None:
        self.start_time = time.time()

        self.config = self.application_config()

        self.app = settings.get('app')
        self.app_module = settings.get('app_module')
        self.app_root = app_root

        self.xml = frontik.producers.xml_producer.XMLProducerFactory(self)
        self.json = frontik.producers.json_producer.JsonProducerFactory(self)

        self.available_integrations: list[integrations.Integration] = []
        self.tornado_http_client: Optional[AIOHttpClientWrapper] = None
        self.http_client_factory: HttpClientFactory

        # self.router = FrontikRouter(self)
        #
        # core_handlers: list[Any] = [
        #     (r'/version/?', VersionHandler),
        #     (r'/status/?', StatusHandler),
        #     (r'.*', self.router),
        # ]
        # if options.debug:
        #     core_handlers.insert(0, (r'/pydevd/?', PydevdHandler))

        self.statsd_client: Union[StatsDClient, StatsDClientStub] = create_statsd_client(options, self)

        init_workers_count_down = multiprocessing.Value(c_int, options.workers)
        master_done = multiprocessing.Value(c_bool, False)
        count_down_lock = multiprocessing.Lock()
        self.worker_state = WorkerState(init_workers_count_down, master_done, count_down_lock)  # type: ignore

        self.returned_value_handlers: ReturnedValueHandlers = get_default_returned_value_handlers()

        # super().__init__(core_handlers)

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
        # self.transforms.insert(0, partial(DebugTransform, self))  # type: ignore

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

    # def find_handler(self, request, **kwargs):
    #     request_id = request.headers.get('X-Request-Id')
    #     if request_id is None:
    #         request_id = FrontikApplication.next_request_id()
    #     if options.validate_request_id:
    #         check_request_id(request_id)
    #
    #     def wrapped_in_context(func: Callable) -> Callable:
    #         def wrapper(*args, **kwargs):
    #             with request_context.request_context(request, request_id):
    #                 return func(*args, **kwargs)
    #
    #         return wrapper
    #
    #     delegate: httputil.HTTPMessageDelegate = wrapped_in_context(super().find_handler)(request, **kwargs)
    #     delegate.headers_received = wrapped_in_context(delegate.headers_received)  # type: ignore
    #     delegate.data_received = wrapped_in_context(delegate.data_received)  # type: ignore
    #     delegate.finish = wrapped_in_context(delegate.finish)  # type: ignore
    #     delegate.on_connection_close = wrapped_in_context(delegate.on_connection_close)  # type: ignore
    #
    #     return delegate

    # def reverse_url(self, name: str, *args: Any, **kwargs: Any) -> str:
    #     return self.router.reverse_url(name, *args, **kwargs)

    # def application_urls(self) -> list[tuple]:
    #     return [('', FileMappingRouter(importlib.import_module(f'{self.app_module}.pages')))]
    #
    # def application_404_handler(self, request: HTTPServerRequest) -> tuple[type[PageHandler], dict]:
    #     return ErrorHandler, {'status_code': 404}

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
        # if not options.log_json:
        #     super().log_request(handler)
        #     return

        request_time = int(1000.0 * (time.time() - handler.request_start_time))
        extra = {
            'ip': request.client.host,
            'rid': request_context.get_request_id(),
            'status': handler.get_status(),
            'time': request_time,
            'method': request.method,
            'uri': repr(request.url),
        }

        handler_name = request_context.get_handler_name()
        if handler_name:
            extra['controller'] = handler_name

        JSON_REQUESTS_LOGGER.info('', extra={CUSTOM_JSON_EXTRA: extra})

    def get_kafka_producer(self, producer_name: str) -> Optional[AIOKafkaProducer]:  # pragma: no cover
        pass

    async def custom_404(self, request: Request, _):
        for pattern, route, cls in regex_mapping:
            if pattern.match(request.url.path):
                request.state.cls = cls
                fa_handler = route.get_route_handler()
                response = await fa_handler(request)

                return response

        raise RuntimeError('krasivoe 404')
