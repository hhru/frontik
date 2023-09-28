from __future__ import annotations
import asyncio
import gc
import importlib
import logging
import multiprocessing
import os.path
import re
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from dataclasses import asdict
from typing import TYPE_CHECKING

from http_client.options import options as http_client_options
import tornado.autoreload
import tornado.httpserver
import tornado.ioloop

from frontik.app import FrontikApplication
from frontik.config_parser import parse_configs
from frontik.loggers import MDC
from frontik.options import options
from frontik.process import fork_workers
from frontik.service_discovery import UpstreamUpdateListener

if TYPE_CHECKING:
    from typing import Coroutine
    from multiprocessing.synchronize import Lock as LockBase
    from asyncio import Future
    from tornado.platform.asyncio import BaseAsyncIOLoop

log = logging.getLogger('server')


def main(config_file:str|None=None) -> None:
    parse_configs(config_files=config_file)

    if options.app is None:
        log.exception('no frontik application present (`app` option is not specified)')
        sys.exit(1)

    log.info('starting application %s', options.app)

    app_class_name: str|None
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
                app=app,
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


def _run_worker(app: FrontikApplication, count_down_lock: LockBase, need_to_init: bool, pipe: int | None) -> None:
    gc.enable()
    MDC.init('worker')

    try:
        import uvloop
    except ImportError:
        log.info('There is no installed uvloop; use asyncio event loop')
    else:
        uvloop.install()

    ioloop: BaseAsyncIOLoop = tornado.ioloop.IOLoop.current()  # type: ignore
    executor = ThreadPoolExecutor(options.common_executor_pool_size)
    ioloop.asyncio_loop.set_default_executor(executor)
    initialize_application_task = ioloop.asyncio_loop.create_task(
        _init_app(app, ioloop, count_down_lock, need_to_init, pipe)
    )

    def initialize_application_task_result_handler(future):
        if future.exception():
            ioloop.stop()

    initialize_application_task.add_done_callback(initialize_application_task_result_handler)
    ioloop.start()
    # to raise init exception if any
    initialize_application_task.result()


async def run_server(app: FrontikApplication, ioloop: BaseAsyncIOLoop, need_to_register_in_service_discovery: bool) -> None:
    """Starts Frontik server for an application"""

    log.info('starting server on %s:%s', options.host, options.port)
    http_server = tornado.httpserver.HTTPServer(app, xheaders=options.xheaders)
    http_server.bind(options.port, options.host, reuse_port=options.reuse_port)
    http_server.start()

    if options.autoreload:
        tornado.autoreload.start(1000)

    def sigterm_handler(signum, frame):
        log.info('requested shutdown, shutting down server on %s:%d', options.host, options.port)
        ioloop.add_callback_from_signal(server_stop)

    def ioloop_is_running() -> bool:
        return ioloop.asyncio_loop.is_running()

    def server_stop():
        ioloop.asyncio_loop.create_task(_deinit_app(app, need_to_register_in_service_discovery))
        http_server.stop()

        if ioloop_is_running():
            log.info('going down in %s seconds', options.stop_timeout)

            def ioloop_stop():
                if ioloop_is_running():
                    log.info('stopping IOLoop')
                    ioloop.stop()
                    log.info('stopped')

            ioloop.asyncio_loop.call_later(options.stop_timeout, ioloop_stop)

    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)


async def _init_app(
    app: FrontikApplication, ioloop: BaseAsyncIOLoop, count_down_lock: LockBase,
        need_to_register_in_service_discovery: bool,
        pipe: int | None
) -> None:
    await app.init()
    if not need_to_register_in_service_discovery and pipe is not None:
        app.upstream_update_listener = UpstreamUpdateListener(app.upstream_manager, pipe)
    await run_server(app, ioloop, need_to_register_in_service_discovery)
    log.info(f'Successfully inited application {app.app}')
    with count_down_lock:
        app.init_workers_count_down.value -= 1
        log.info(f'worker is up, remaining workers = {app.init_workers_count_down.value}')
    if need_to_register_in_service_discovery:
        register_task = ioloop.asyncio_loop.create_task(app.service_discovery_client.register_service())

        def register_task_result_handler(future):
            if future.exception():
                ioloop.stop()
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
