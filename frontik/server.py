import asyncio
import contextlib
import gc
import importlib
import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Lock
from typing import Callable, Optional

import tornado.autoreload
from http_client.balancing import Upstream
from tornado.httpserver import HTTPServer

from frontik.app import FrontikApplication
from frontik.config_parser import parse_configs
from frontik.loggers import MDC
from frontik.options import options
from frontik.process import fork_workers
from frontik.pydebug import try_init_debugger
from frontik.util.gc import enable_gc

log = logging.getLogger('server')


def main(config_file: Optional[str] = None) -> None:
    try_init_debugger()

    parse_configs(config_files=config_file)

    if options.app_class is None:
        log.exception('no frontik application present (`app_class` option is not specified)')
        sys.exit(1)

    log.info('starting application %s', options.app_class)

    try:
        app_module_name, app_class_name = options.app_class.rsplit('.', 1)
        app_module = importlib.import_module(app_module_name)
    except Exception as e:
        log.exception('failed to import application "%s": %s', options.app_class, e)
        sys.exit(1)

    application = getattr(app_module, app_class_name) if app_class_name is not None else FrontikApplication

    try:
        app = application()

        gc.disable()
        gc.collect()
        gc.freeze()
        if options.workers != 1:
            fork_workers(
                worker_state=app.worker_state,
                num_workers=options.workers,
                master_before_fork_action=partial(_master_before_fork_action, app),
                master_after_fork_action=partial(_master_after_fork_action, app),
                master_before_shutdown_action=partial(_master_before_shutdown_action, app),
                worker_function=partial(_run_worker, app),
                worker_listener_handler=partial(_worker_listener_handler, app),
            )
        else:
            # run in single process mode
            enable_gc()
            _run_worker(app)
    except Exception as e:
        log.exception('frontik application exited with exception: %s', e)
        sys.exit(1)


def _master_before_fork_action(app: FrontikApplication) -> tuple[dict, Optional[Lock]]:
    async def async_actions() -> None:
        await app.install_integrations()
        if (local_before_fork_action := getattr(app, 'before_fork_action', None)) is not None:
            await local_before_fork_action()

    asyncio.run(async_actions())
    return app.service_discovery.get_upstreams_with_lock()


def _master_after_fork_action(
    app: FrontikApplication,
    update_shared_data_hook: Optional[Callable],
) -> None:
    if update_shared_data_hook is None:
        return

    app.service_discovery.set_update_shared_data_hook(update_shared_data_hook)
    app.service_discovery.send_updates()  # send in case there were updates between worker creation and this point
    app.service_discovery.register_service()


def _master_before_shutdown_action(app: FrontikApplication) -> None:
    asyncio.run(_deinit_app(app, with_delay=False))


def _worker_listener_handler(app: FrontikApplication, data: list[Upstream]) -> None:
    app.service_discovery.update_upstreams(data)


def _run_worker(app: FrontikApplication) -> None:
    MDC.init('worker')

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


def run_server(frontik_app: FrontikApplication) -> None:
    """Starts Frontik server for an application"""
    loop = asyncio.get_event_loop()
    log.info('starting server on %s:%s', options.host, options.port)
    http_server = HTTPServer(frontik_app, xheaders=options.xheaders, max_body_size=options.max_body_size)
    http_server.bind(options.port, options.host, reuse_port=options.reuse_port)
    http_server.start()

    if options.autoreload:
        tornado.autoreload.start(1000)

    def worker_sigterm_handler(_signum, _frame):
        log.info('requested shutdown, shutting down server on %s:%d', options.host, options.port)
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(server_stop)

    def server_stop():
        deinit_task = loop.create_task(_deinit_app(frontik_app, with_delay=True))
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


async def _init_app(frontik_app: FrontikApplication) -> None:
    await frontik_app.init()
    run_server(frontik_app)
    log.info('Successfully inited application %s', frontik_app.app_name)
    with frontik_app.worker_state.count_down_lock:
        frontik_app.worker_state.init_workers_count_down.value -= 1
        log.info('worker is up, remaining workers = %s', frontik_app.worker_state.init_workers_count_down.value)

    frontik_app.service_discovery.register_service()


async def _deinit_app(app: FrontikApplication, with_delay: bool) -> None:
    app.service_discovery.deregister_service_and_close()

    if with_delay:
        await asyncio.sleep(options.stop_timeout)

    try:
        if app.http_client is not None:
            await asyncio.wait_for(app.http_client.http_client_impl.client_session.close(), timeout=1.0)

        for integration in app.available_integrations:
            integration.deinitialize_app(app)

        log.info('Successfully deinited application')

    except Exception as e:
        log.exception('failed to deinit, deinit returned: %s', e)
