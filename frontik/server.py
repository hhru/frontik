from __future__ import annotations

import asyncio
import contextlib
import gc
import importlib
import logging
import multiprocessing
import os.path
import re
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from functools import partial
from typing import TYPE_CHECKING

import tornado.autoreload
from http_client.options import options as http_client_options
from tornado.httpserver import HTTPServer

from frontik.app import FrontikApplication
from frontik.config_parser import parse_configs
from frontik.loggers import MDC
from frontik.options import options
from frontik.process import fork_workers
from frontik.service_discovery import UpstreamUpdateListener

if TYPE_CHECKING:
    from asyncio import Future
    from collections.abc import Coroutine
    from multiprocessing.synchronize import Lock as LockBase

log = logging.getLogger('server')


def main(config_file: str | None = None) -> None:
    parse_configs(config_files=config_file)

    if options.app is None:
        log.exception('no frontik application present (`app` option is not specified)')
        sys.exit(1)

    log.info('starting application %s', options.app)

    app_class_name: str | None
    try:
        if options.app_class is not None and re.match(r'^\w+\.', options.app_class):
            app_module_name, app_class_name = options.app_class.rsplit('.', 1)
        else:
            app_module_name = options.app
            app_class_name = options.app_class

        module = importlib.import_module(app_module_name)
    except Exception as e:
        log.exception('failed to import application module "%s": %s', options.app, e)

        sys.exit(1)

    if app_class_name is not None and not hasattr(module, app_class_name):
        log.exception('application class "%s" not found', options.app_class)
        sys.exit(1)

    application = getattr(module, app_class_name) if app_class_name is not None else FrontikApplication

    try:
        app = application(
            app_root=os.path.dirname(str(module.__file__)),
            app_module=app_module_name,
            **{**asdict(options), **asdict(http_client_options)},
        )
        count_down_lock = multiprocessing.Lock()

        gc.disable()
        gc.collect()
        gc.freeze()
        if options.workers != 1:
            fork_workers(
                partial(_run_worker, app, count_down_lock, False),
                init_workers_count_down=app.init_workers_count_down,
                num_workers=options.workers,
                after_workers_up_action=lambda: {
                    app.upstream_caches.send_updates(),
                    app.service_discovery_client.register_service(),
                },
                before_workers_shutdown_action=app.service_discovery_client.deregister_service_and_close,
                children_pipes=app.children_pipes,
            )
        else:
            # run in single process mode
            _run_worker(app, count_down_lock, True, None)
    except Exception as e:
        log.exception('frontik application exited with exception: %s', e)
        sys.exit(1)


def _run_worker(
    app: FrontikApplication,
    count_down_lock: LockBase,
    need_to_register_in_service_discovery: bool,
    read_pipe_fd: int | None,
) -> None:
    gc.enable()
    MDC.init('worker')

    try:
        import uvloop
    except ImportError:
        log.info('There is no installed uvloop; use asyncio event loop')
    else:
        uvloop.install()

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(options.common_executor_pool_size)
    loop.set_default_executor(executor)
    initialize_application_task = loop.create_task(
        _init_app(app, count_down_lock, need_to_register_in_service_discovery, read_pipe_fd),
    )

    def initialize_application_task_result_handler(future):
        if future.exception():
            loop.stop()

    initialize_application_task.add_done_callback(initialize_application_task_result_handler)
    loop.run_forever()
    # to raise init exception if any
    initialize_application_task.result()


async def run_server(
    app: FrontikApplication,
    need_to_register_in_service_discovery: bool,
) -> None:
    """Starts Frontik server for an application"""
    loop = asyncio.get_event_loop()
    log.info('starting server on %s:%s', options.host, options.port)
    http_server = HTTPServer(app, xheaders=options.xheaders)
    http_server.bind(options.port, options.host, reuse_port=options.reuse_port)
    http_server.start()

    if options.autoreload:
        tornado.autoreload.start(1000)

    def sigterm_handler(signum, frame):
        log.info('requested shutdown, shutting down server on %s:%d', options.host, options.port)
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(server_stop)

    def server_stop():
        loop.create_task(_deinit_app(app, need_to_register_in_service_discovery))
        http_server.stop()

        if loop.is_running():
            log.info('going down in %s seconds', options.stop_timeout)

            def ioloop_stop():
                if loop.is_running():
                    log.info('stopping IOLoop')
                    loop.stop()
                    log.info('stopped')

            loop.call_later(options.stop_timeout, ioloop_stop)

    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)


async def _init_app(
    app: FrontikApplication,
    count_down_lock: LockBase,
    need_to_register_in_service_discovery: bool,
    read_pipe_fd: int | None,
) -> None:
    await app.init()
    if not need_to_register_in_service_discovery and read_pipe_fd is not None:
        app.upstream_update_listener = UpstreamUpdateListener(app.upstream_manager, read_pipe_fd)
    await run_server(app, need_to_register_in_service_discovery)
    log.info('Successfully inited application %s', app.app)
    with count_down_lock:
        app.init_workers_count_down.value -= 1
        log.info('worker is up, remaining workers = %s', app.init_workers_count_down.value)
    if need_to_register_in_service_discovery:
        loop = asyncio.get_event_loop()
        register_task = loop.create_task(app.service_discovery_client.register_service())

        def register_task_result_handler(future):
            if future.exception():
                loop.stop()
                future.result()

        register_task.add_done_callback(register_task_result_handler)


async def _deinit_app(app: FrontikApplication, need_to_register_in_service_discovery: bool) -> None:
    deinit_futures: list[Future | Coroutine | None] = []

    if need_to_register_in_service_discovery:
        deregistration = app.service_discovery_client.deregister_service_and_close()
        deinit_futures = [asyncio.wait_for(deregistration, timeout=options.stop_timeout)]

    deinit_futures.extend([integration.deinitialize_app(app) for integration in app.available_integrations])

    if app.tornado_http_client is not None:
        deinit_futures.append(app.tornado_http_client.client_session.close())

    if deinit_futures:
        try:
            await asyncio.gather(*[future for future in deinit_futures if future])
            log.info('Successfully deinited application')
        except Exception as e:
            log.exception('failed to deinit, deinit returned: %s', e)
