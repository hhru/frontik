import asyncio
import contextlib
import gc
import importlib
import logging
import signal
import socket
import sys
from asyncio import Future
from collections.abc import Awaitable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from functools import partial
from threading import Lock
from typing import Any, Callable, Optional, Union
import multiprocessing
from ctypes import c_bool, c_int
import pickle
import os

import anyio
import tornado.autoreload
import uvicorn
from http_client.balancing import Upstream
from starlette.middleware import Middleware

from frontik.app import FrontikApplication
from frontik.config_parser import parse_configs
from frontik.loggers import MDC
from frontik.options import options
from frontik.process import fork_workers, WorkerState
from frontik.routing import RoutingMiddleware, import_all_pages, routers
from frontik.options import set_opts
from frontik.loggers import bootstrap_core_logging

log = logging.getLogger('server')
LISTENER_TASK = set()  # save task from garbage collector


def main(config_file: Optional[str] = None) -> None:
    parse_configs(config_files=config_file)

    if options.app is None:
        log.exception('no frontik application present (`app` option is not specified)')
        sys.exit(1)

    log.info('starting application %s', options.app)

    try:
        app_module = importlib.import_module(options.app)
        app_class_name = None
        app_module_name = options.app
    except Exception:
        try:
            app_module_name, app_class_name = options.app.rsplit('.', 1)
            app_module = importlib.import_module(app_module_name)
        except Exception as e:
            log.exception('failed to import application module "%s": %s', options.app, e)

            sys.exit(1)

    if app_class_name is not None and not hasattr(app_module, app_class_name):
        log.exception('application class "%s" not found', options.app_class)
        sys.exit(1)

    app_t = app_module_name, app_class_name

    init_workers_count_down = multiprocessing.Value(c_int, options.workers)
    master_done = multiprocessing.Value(c_bool, False)
    count_down_lock = multiprocessing.Lock()
    worker_state = WorkerState(init_workers_count_down, master_done, count_down_lock)  # type: ignore

    try:
        # app = application(app_module_name)

        gc.disable()
        gc.collect()
        gc.freeze()
        if options.workers != 1 or True:
            fork_workers(
                worker_state=worker_state,
                num_workers=options.workers,
                master_function=partial(_multi_worker_master_function, app_t),
                master_before_shutdown_action=_master_before_shutdown_action,
                worker_function=partial(_run_worker, app_t),
            )
        else:
            # run in single process mode
            gc.enable()
            _run_worker(app_t, options, worker_state)
    except Exception as e:
        log.exception('frontik application exited with exception: %s', e)
        sys.exit(1)


app_refs: list[FrontikApplication] = []
ready_for_serve = asyncio.Future()


def _multi_worker_master_function(
    app_t: tuple,
    upstreams: dict[str, Upstream],
    upstreams_lock: Lock,
    send_to_all_workers: Callable,
) -> None:
    log.info('master function: create app')
    app_module_name, app_class_name = app_t
    app_module = importlib.import_module(app_module_name)
    application = getattr(app_module, app_class_name) if app_class_name is not None else FrontikApplication
    app = application(app_module_name)
    if len(app_refs) == 0:
        app_refs.append(app)
    else:
        raise RuntimeError('(master) app instantiation got race condition')

    log.info('master function: app created, create upstream manager')
    app.create_upstream_manager(upstreams, upstreams_lock, send_to_all_workers, with_consul=options.consul_enabled)
    log.info('master function: upstream manager created, register in consul')
    app.upstream_manager.register_service()


def _master_before_shutdown_action():
    if len(app_refs) == 0:
        return
    app_refs[0].upstream_manager.deregister_service_and_close()


async def _worker_listener() -> None:
    while not os.path.exists('/tmp/my_consul'):
        await asyncio.sleep(0.1)

    while len(app_refs) == 0:
        await asyncio.sleep(0.1)

    while len(os.listdir('/tmp/my_consul')) == 0:
        await asyncio.sleep(0.1)

    last_fn: float = None
    log.info(f'start watching consul data')

    try:
        while True:
            await asyncio.sleep(0.1)

            file_list: list[float] = [float(fn) for fn in os.listdir('/tmp/my_consul')]
            if len(file_list) == 0:
                continue

            file_list.sort()
            if last_fn == file_list[-1]:
                if not ready_for_serve.done():
                    ready_for_serve.set_result(True)
                continue

            fn = None
            try:
                for fn in file_list:
                    if last_fn and fn <= last_fn:
                        continue

                    if fn == file_list[-1]:
                        await asyncio.sleep(0.1)

                    log.info(f'read new consul data from /tmp/my_consul/{fn}')
                    with open('/tmp/my_consul/' + str(fn), 'rb') as c_file:
                        data = pickle.load(c_file)

                    log.info(f'received data from /tmp/my_consul/{fn}')
                    _worker_listener_handler(data)
                    last_fn = fn
            except Exception as exc:
                log.info(f'something went wrong with reading /tmp/my_consul/{fn} ----- {type(exc)} {exc}')
                continue
    except Exception as ex:
        log.exception(f'fatal error with reading consul ----- {type(ex)} {ex}')
        raise


def _worker_listener_handler(data: list[Upstream]) -> None:
    if len(app_refs) == 0:
        return
    app_refs[0].upstream_manager.update_upstreams(data)


def _run_worker(app_t: tuple, options2, worker_state) -> None:
    gc.enable()
    MDC.init('worker')

    worker_state.is_master = False
    set_opts(options2)
    bootstrap_core_logging(options.log_level, options.log_json, options.suppressed_loggers)

    loop = asyncio.get_event_loop()

    app_module_name, app_class_name = app_t
    app_module = importlib.import_module(app_module_name)
    application = getattr(app_module, app_class_name) if app_class_name is not None else FrontikApplication
    app = application(app_module_name)

    app.worker_state = worker_state

    executor = ThreadPoolExecutor(options.common_executor_pool_size)
    loop.set_default_executor(executor)
    init_task = loop.create_task(_init_app(app))

    log.info(f'create listener task loop={id(loop)}')
    task11 = loop.create_task(_worker_listener())
    LISTENER_TASK.add(task11)

    def initialize_application_task_result_handler(task):
        if task.exception():
            loop.stop()

    init_task.add_done_callback(initialize_application_task_result_handler)
    loop.run_forever()

    if init_task.done() and init_task.exception():
        raise RuntimeError('worker failed') from init_task.exception()


async def periodic_task(callback: Callable, check_timedelta: timedelta) -> None:
    while True:
        await asyncio.sleep(check_timedelta.total_seconds())
        callback()


def bind_socket(host: str, port: int) -> socket.socket:
    sock = socket.socket(family=socket.AF_INET)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

    try:
        sock.bind((host, port))
    except OSError as exc:
        log.error(exc)
        sys.exit(1)

    sock.set_inheritable(True)
    return sock


def run_server(frontik_app: FrontikApplication, sock: Optional[socket.socket] = None) -> Awaitable:
    """Starts Frontik server for an application"""
    loop = asyncio.get_event_loop()
    log.info('starting server on %s:%s', options.host, options.port)

    anyio.to_thread.run_sync = anyio_noop
    import_all_pages(frontik_app.app_module_name)
    fastapi_app = frontik_app.fastapi_app
    setattr(fastapi_app, 'frontik_app', frontik_app)
    for router in routers:
        fastapi_app.include_router(router)

    # because on idx=0 we have OpenTelemetryMiddleware
    fastapi_app.user_middleware.insert(1, Middleware(RequestCancelledMiddleware))
    fastapi_app.user_middleware.insert(1, Middleware(RoutingMiddleware))  # should be last, because it ignores call_next

    config = uvicorn.Config(
        fastapi_app,
        host=options.host,
        port=options.port,
        log_level='critical',
        loop='none',
        log_config=None,
        access_log=False,
        server_header=False,
        lifespan='off',
    )
    server = uvicorn.Server(config)

    if options.autoreload:
        check_timedelta = timedelta(milliseconds=500)
        modify_times: dict[str, float] = {}
        reload = partial(tornado.autoreload._reload_on_update, modify_times)

        server_task = asyncio.gather(server._serve(), periodic_task(reload, check_timedelta))
    else:
        if sock is None:
            sock = bind_socket(options.host, options.port)
        server_task = loop.create_task(server._serve([sock]))  # type: ignore

    def worker_sigterm_handler(_signum, _frame):
        log.info('requested shutdown, shutting down server on %s:%d', options.host, options.port)
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(server_stop)

    def server_stop():
        log.info('going down in %s seconds', options.stop_timeout)

        def ioloop_stop(_deinit_task):
            if loop.is_running():
                log.info('stopping IOLoop')
                loop.stop()
                log.info('stopped')

        deinit_task = loop.create_task(_deinit_app(frontik_app, server))
        deinit_task.add_done_callback(ioloop_stop)

    signal.signal(signal.SIGTERM, worker_sigterm_handler)
    signal.signal(signal.SIGINT, worker_sigterm_handler)

    return server_task


async def _init_app(frontik_app: FrontikApplication) -> None:
    await frontik_app.init()

    if len(app_refs) == 0:
        app_refs.append(frontik_app)
    else:
        raise RuntimeError('(worker) app instantiation got race condition')

    server_task = run_server(frontik_app)
    log.info('Successfully inited application %s', frontik_app.app_name)
    with frontik_app.worker_state.count_down_lock:
        frontik_app.worker_state.init_workers_count_down.value -= 1
        log.info('worker is up, remaining workers = %s', frontik_app.worker_state.init_workers_count_down.value)
    await ready_for_serve
    await server_task


async def kill_server(app: FrontikApplication, server: uvicorn.Server) -> None:
    await asyncio.sleep(options.stop_timeout)
    if app.http_client is not None:
        await app.http_client.client_session.close()
    server.should_exit = True


async def _deinit_app(app: FrontikApplication, server: uvicorn.Server) -> None:
    deinit_futures: list[Optional[Union[Future, Coroutine]]] = [kill_server(app, server)]
    deinit_futures.extend([integration.deinitialize_app(app) for integration in app.available_integrations])

    app.upstream_manager.deregister_service_and_close()

    try:
        await asyncio.gather(*[future for future in deinit_futures if future])
        log.info('Successfully deinited application')
    except Exception as e:
        log.exception('failed to deinit, deinit returned: %s', e)


class RequestCancelledMiddleware:
    # https://github.com/tiangolo/fastapi/discussions/11360
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        queue: asyncio.Queue = asyncio.Queue()

        async def message_poller(_sentinel: Any, _handler_task: Any) -> Any:
            nonlocal queue
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    _handler_task.cancel()
                    return _sentinel

                await queue.put(message)

        sentinel = object()
        handler_task = asyncio.create_task(self.app(scope, queue.get, send))
        poller_task = asyncio.create_task(message_poller(sentinel, handler_task))
        poller_task.done()

        try:
            return await handler_task
        except asyncio.CancelledError:
            pass


def anyio_noop(*_args, **_kwargs):
    raise RuntimeError(f'trying to use {_args[0]}')
