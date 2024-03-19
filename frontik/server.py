import asyncio
import contextlib
import gc
import importlib
import logging
import os.path
import re
import signal
import sys
from asyncio import Future
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from functools import partial
from threading import Lock
from typing import Callable, Optional, Union

import tornado.autoreload
from http_client.balancing import Upstream
from http_client.options import options as http_client_options
from tornado.httpserver import HTTPServer

from frontik.app import FrontikApplication
from frontik.config_parser import parse_configs
from frontik.loggers import MDC
from frontik.options import options
from frontik.process import fork_workers

log = logging.getLogger('server')


def main(config_file: Optional[str] = None) -> None:
    parse_configs(config_files=config_file)

    if options.app is None:
        log.exception('no frontik application present (`app` option is not specified)')
        sys.exit(1)

    log.info('starting application %s', options.app)

    app_class_name: Optional[str]
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

        gc.disable()
        gc.collect()
        gc.freeze()
        if options.workers != 1:
            fork_workers(
                worker_state=app.worker_state,
                num_workers=options.workers,
                master_function=partial(_multi_worker_master_function, app),
                master_before_shutdown_action=lambda: app.upstream_manager.deregister_service_and_close(),  # noqa PLW0108
                worker_function=partial(_run_worker, app),
                worker_listener_handler=partial(_worker_listener_handler, app),
            )
        else:
            # run in single process mode
            gc.enable()
            _run_worker(app)
    except Exception as e:
        log.exception('frontik application exited with exception: %s', e)
        sys.exit(1)


def _multi_worker_master_function(
    app: FrontikApplication,
    upstreams: dict[str, Upstream],
    upstreams_lock: Lock,
    send_to_all_workers: Callable,
) -> None:
    app.create_upstream_manager(upstreams, upstreams_lock, send_to_all_workers, with_consul=options.consul_enabled)
    app.upstream_manager.register_service()


def _worker_listener_handler(app: FrontikApplication, data: list[Upstream]) -> None:
    app.upstream_manager.update_upstreams(data)


def _run_worker(app: FrontikApplication) -> None:
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
    initialize_application_task = loop.create_task(_init_app(app))

    def initialize_application_task_result_handler(future):
        if future.exception():
            loop.stop()

    initialize_application_task.add_done_callback(initialize_application_task_result_handler)
    loop.run_forever()
    # to raise init exception if any
    initialize_application_task.result()


def run_server(app: FrontikApplication) -> None:
    """Starts Frontik server for an application"""
    loop = asyncio.get_event_loop()
    log.info('starting server on %s:%s', options.host, options.port)
    http_server = HTTPServer(app, xheaders=options.xheaders)
    http_server.bind(options.port, options.host, reuse_port=options.reuse_port)
    http_server.start()

    if options.autoreload:
        tornado.autoreload.start(1000)

    def worker_sigterm_handler(_signum, _frame):
        log.info('requested shutdown, shutting down server on %s:%d', options.host, options.port)
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(server_stop)

    def server_stop():
        deinit_task = loop.create_task(_deinit_app(app))
        http_server.stop()

        if loop.is_running():
            log.info('going down in %s seconds', options.stop_timeout)

            def ioloop_stop(_deinit_task):
                if loop.is_running():
                    log.info('stopping IOLoop')
                    loop.stop()
                    log.info('stopped')

            deinit_task.add_done_callback(ioloop_stop)

    signal.signal(signal.SIGTERM, worker_sigterm_handler)
    signal.signal(signal.SIGINT, worker_sigterm_handler)


async def _init_app(app: FrontikApplication) -> None:
    await app.init()
    run_server(app)
    log.info('Successfully inited application %s', app.app)
    with app.worker_state.count_down_lock:
        app.worker_state.init_workers_count_down.value -= 1
        log.info('worker is up, remaining workers = %s', app.worker_state.init_workers_count_down.value)


async def _deinit_app(app: FrontikApplication) -> None:
    deinit_futures: list[Optional[Union[Future, Coroutine]]] = []

    app.upstream_manager.deregister_service_and_close()

    deinit_futures.extend([integration.deinitialize_app(app) for integration in app.available_integrations])

    if deinit_futures:
        try:
            await asyncio.gather(*[future for future in deinit_futures if future])
            log.info('Successfully deinited application')
        except Exception as e:
            log.exception('failed to deinit, deinit returned: %s', e)

    await asyncio.sleep(options.stop_timeout)
    if app.tornado_http_client is not None:
        await app.tornado_http_client.client_session.close()
