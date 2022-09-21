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
from datetime import datetime

from http_client.options import options as http_client_options
import tornado.autoreload
import tornado.httpserver
import tornado.ioloop
from tornado.httputil import HTTPServerRequest
from tornado.platform.asyncio import BaseAsyncIOLoop

from frontik.app import FrontikApplication
from frontik.config_parser import parse_configs
from frontik.loggers import bootstrap_logger, MDC
from frontik.options import options
from frontik.process import fork_workers
from frontik.request_context import get_request
from frontik.service_discovery import UpstreamUpdateListener

log = logging.getLogger('server')
current_callback = None


def main(config_file=None):
    parse_configs(config_files=config_file)

    if options.app is None:
        log.exception('no frontik application present (`app` option is not specified)')
        sys.exit(1)

    log.info('starting application %s', options.app)

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
        app = application(app_root=os.path.dirname(module.__file__), app_module=app_module_name,
                          **{**asdict(options), **asdict(http_client_options)})
        count_down_lock = multiprocessing.Lock()

        gc.disable()
        gc.collect()
        gc.freeze()
        if options.workers != 1:
            fork_workers(partial(_run_worker, app, count_down_lock, False),
                         app=app,
                         init_workers_count_down=app.init_workers_count_down,
                         num_workers=options.workers,
                         after_workers_up_action=lambda: {
                             app.upstream_caches.send_updates(),
                             app.service_discovery_client.register_service()},
                         before_workers_shutdown_action=app.service_discovery_client.deregister_service_and_close,
                         children_pipes=app.children_pipes)
        else:
            # run in single process mode
            _run_worker(app, count_down_lock, True, None)
    except Exception as e:
        log.exception('frontik application exited with exception: %s', e)
        sys.exit(1)


def _run_worker(app, count_down_lock, need_to_init, pipe):
    gc.enable()
    MDC.init('worker')

    try:
        import uvloop
    except ImportError:
        log.info('There is no installed uvloop; use asyncio event loop')
    else:
        uvloop.install()

    ioloop = tornado.ioloop.IOLoop.current()
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


async def run_server(app: FrontikApplication, ioloop: BaseAsyncIOLoop, need_to_register_in_service_discovery):
    """Starts Frontik server for an application"""

    if options.asyncio_task_threshold_sec is not None:
        slow_tasks_logger = bootstrap_logger('slow_tasks', logging.WARNING)

        import reprlib

        reprlib.aRepr.maxother = 256
        wrap_handle_with_time_logging(app, slow_tasks_logger)

    log.info('starting server on %s:%s', options.host, options.port)
    http_server = tornado.httpserver.HTTPServer(app, xheaders=options.xheaders)
    http_server.bind(options.port, options.host, reuse_port=options.reuse_port)
    http_server.start()

    if options.autoreload:
        tornado.autoreload.start(1000)

    def sigterm_handler(signum, frame):
        log.info('requested shutdown, shutting down server on %s:%d', options.host, options.port)
        ioloop.add_callback_from_signal(server_stop)

    def ioloop_is_running():
        return ioloop.asyncio_loop.is_running()

    def server_stop():
        ioloop.asyncio_loop.create_task(_deinit_app(app, ioloop, need_to_register_in_service_discovery))
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


async def _init_app(app: FrontikApplication, ioloop: BaseAsyncIOLoop, count_down_lock,
                    need_to_register_in_service_discovery, pipe):
    await app.init()
    if not need_to_register_in_service_discovery:
        app.upstream_update_listener = UpstreamUpdateListener(app.http_client_factory, pipe)
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


async def _deinit_app(app: FrontikApplication, ioloop: BaseAsyncIOLoop, need_to_register_in_service_discovery):
    if need_to_register_in_service_discovery:
        deregistration = app.service_discovery_client.deregister_service_and_close()
        deinit_futures = [asyncio.wait_for(deregistration, timeout=options.stop_timeout)]
    else:
        deinit_futures = []
    deinit_futures.extend([integration.deinitialize_app(app) for integration in app.available_integrations])
    if deinit_futures:
        try:
            await asyncio.gather(*[future for future in deinit_futures if future], loop=ioloop.asyncio_loop)
            log.info('Successfully deinited application')
        except Exception as e:
            log.exception('failed to deinit, deinit returned: %s', e)


def wrap_handle_with_time_logging(app: FrontikApplication, slow_tasks_logger):
    old_run = asyncio.Handle._run

    def _log_slow_tasks(ts: datetime, handle: asyncio.Handle, delta: float):
        delta_ms = delta * 1000
        app.statsd_client.time('long_task.time', int(delta_ms))
        trace_id = get_trace_id(handle)
        ts = ts.strftime("%Y-%m-%d %H:%M:%S.%f")
        slow_tasks_logger.warning('ts: %s, trace_id: %s, %s took %.2fms', ts, trace_id, handle, delta_ms)

        if options.asyncio_task_critical_threshold_sec and delta >= options.asyncio_task_critical_threshold_sec:
            request = get_request() or HTTPServerRequest('GET', '/asyncio_long_task_stub')
            sentry_logger = app.get_sentry_logger(request)
            sentry_logger.update_user_info(ip='127.0.0.1')

            if sentry_logger:
                slow_tasks_logger.warning('no sentry logger available')
                sentry_logger.capture_message(f'{handle} took {delta_ms:.2f} ms', stack=True)

    def run(self):
        global current_callback
        current_callback = self
        start_time = self._loop.time()
        old_run(self)
        delta = self._loop.time() - start_time
        end_time = datetime.now()

        if delta >= options.asyncio_task_threshold_sec:
            self._context.run(partial(_log_slow_tasks, end_time, self, delta))

    asyncio.Handle._run = run


def get_trace_id(handle):
    try:
        return hex(list(next(handle._context.items())[1].values())[0]._context.trace_id)
    except Exception:
        return None
