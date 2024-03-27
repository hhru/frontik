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
import pkgutil
from http_client import HttpClient
from starlette.middleware.base import Response
from fastapi import Depends

app_logger = logging.getLogger('http_client')

core_router = APIRouter()
routers = [core_router]
# mega_http_client: HttpClient = None


def fill_router(frontik_app):
    """
    понял мы пройдемся по всем файлам в pages и импортнем файлы
    там будут странички импортящие роутеры
    а роутеры должны быть кастом роутеры и они тогда в список добавятся
    и мы тогда их апу скормим кайф
    """
    package_name = f'{frontik_app.app_module}.pages'
    package = sys.modules[package_name]
    for _loader, name, _is_pkg in pkgutil.walk_packages(package.__path__):
        importlib.import_module(package_name + '.' + name)


class CustomRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        routers.append(self)


def build_self(cls: type(PageHandler)):  # здесь надо сделать апгрейд
    async def make_frontik_self(request: Request):
        # old_handler = request.state.handler
        """
        депки из декоратора раньше выполняются чем селфгеттер(((
        хз че с этим делать
        """

        """
        делаем вид что фронтикхендлер на уровне роутера не нужен был
        и создаем только ща под конкретный роут
        хз че будем делать с тем что кто-то делает сет_статус сет_хедер
        """
        print('delau frontik handler')
        new_handler = cls(request.app.frontik_app, request.query_params, request.cookies, request.headers, request.state.start_time)

        # page_handler: PageHandler = cls(request.app.frontik_app, request)
        new_handler.prepare()
        request.state.handler = new_handler
        return new_handler

    return make_frontik_self


async def core_middle_ware(request: Request, call_next):
    print(f'-----core----midlware---')
    request.state.start_time = time.time()

    request_id = request.headers.get('X-Request-Id')
    if request_id is None:
        request_id = FrontikApplication.next_request_id()
    if options.validate_request_id:
        check_request_id(request_id)

    with request_context.request_context(request, request_id):
        try:
            response = await call_next(request)

            if True:  # response.data is empty  будет 100% случаев в начале
                if hasattr(request.state, 'handler'):  # а может быть ручку сделают без селфа? тогда в ней не будет финиш группы
                    handler = request.state.handler
                    handler._handler_finished_notification()
                    await handler.finish_group.get_gathering_future()
                    await handler.finish_group.get_finish_future()

                    # надо еще постпроцы сделать
                    render_result = await handler._postprocess()
                    if render_result is not None:
                        # здесь приедтся самим клепать респонс
                        response = Response(status_code=handler._status, content=render_result)

                    for k, v in handler.new_h_params.items():
                        response.headers[k] = v
                    handler._finished = True

            else:  # response.data is not None
                # чекаем что финиш группа пустая и нет пост процов
                pass

        except MyFinishError as finish_ex:
            # надо прибить финиш группу

            chunk = finish_ex.data
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            elif isinstance(chunk, dict):
                chunk = json.dumps(chunk).replace("</", "<\\/")
                chunk = chunk.encode("utf-8")
            elif isinstance(chunk, bytes):
                pass
            else:
                raise RuntimeError('unexpected type of chunk')

            # должны быть еще хедеры и статус
            response = Response(content=chunk, headers={"Content-Type": "application/json; charset=UTF-8"})

        except MyRedirectError as redirect_ex:
            # надо прибить финиш группу

            url = redirect_ex.url
            response = Response(status_code=302, headers={"Location": url.encode('utf-8')})

    return response


def qq_path() -> str:
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)
    page_file_path = calframe[1].filename
    idx = page_file_path.find('/pages')
    if idx == -1:
        raise RuntimeError('cant generate url path')
    return page_file_path[idx + 6:-3]


@core_router.get('/version')
async def get_version(self=Depends(build_self(PageHandler))):
    self.set_header('Content-Type', 'text/xml')
    self.finish(
        etree.tostring(get_frontik_and_apps_versions(self.application), encoding='utf-8', xml_declaration=True),
    )


@core_router.get('/status')
async def get_status(self=Depends(build_self(PageHandler))):
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

        # global mega_http_client
        # mega_http_client = self.http_client_factory.get_http_client()

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

    def log_request(self, handler):
        # кто теперь это вызывать будет?
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

    def get_kafka_producer(self, producer_name: str) -> Optional[AIOKafkaProducer]:  # pragma: no cover
        pass
