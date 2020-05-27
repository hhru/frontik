import asyncio
import gc
import importlib
import logging
import os.path
import re
import signal
import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Type

import tornado.autoreload
import tornado.httpserver
import tornado.ioloop
from tornado.httputil import HTTPServerRequest
from tornado.options import parse_command_line, parse_config_file
from tornado.platform.asyncio import BaseAsyncIOLoop

from frontik.app import FrontikApplication
from frontik.loggers import bootstrap_logger, bootstrap_core_logging, MDC
from frontik.options import options
from frontik.process import fork_workers
from frontik.request_context import get_request
from frontik.service_discovery import get_sync_service_discovery

log = logging.getLogger('server')


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
        app = application(app_root=os.path.dirname(module.__file__), app_module=app_module_name, **options.as_dict())

        gc.disable()
        gc.collect()
        gc.freeze()
        if options.workers != 1:
            service_discovery_client = get_sync_service_discovery(options, hostname=socket.gethostname())
            fork_workers(partial(_run_worker, app),
                         num_workers=options.workers,
                         after_workers_up_action=service_discovery_client.register_service,
                         before_workers_shutdown_action=service_discovery_client.deregister_service_and_close)
        else:
            # run in single process mode
            _run_worker(app, True)
    except Exception as e:
        log.exception('frontik application exited with exception: %s', e)
        sys.exit(1)


def _run_worker(app, need_to_init=False):
    gc.enable()
    MDC.init('worker')
    ioloop = tornado.ioloop.IOLoop.current()
    executor = ThreadPoolExecutor(options.common_executor_pool_size)
    ioloop.asyncio_loop.set_default_executor(executor)
    initialize_application_task = ioloop.asyncio_loop.create_task(_init_app(app, ioloop, need_to_init))

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
        slow_tasks_logger = bootstrap_logger('slow_tasks', logging.WARNING, use_json_formatter=False)

        import asyncio
        import reprlib

        reprlib.aRepr.maxother = 256
        wrap_handle_with_time_logging(asyncio.Handle, app, slow_tasks_logger)

    log.info('starting server on %s:%s', options.host, options.port)
    http_server = tornado.httpserver.HTTPServer(app, xheaders=options.xheaders)
    http_server.bind(options.port, options.host, reuse_port=options.reuse_port)
    http_server.start()

    if options.autoreload:
        tornado.autoreload.start(1000)

    def sigterm_handler(signum, frame):
        log.info('requested shutdown')
        log.info('shutting down server on %s:%d', options.host, options.port)
        ioloop.add_callback_from_signal(server_stop)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)

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


def parse_configs(config_files):
    """Reads command line options / config file and bootstraps logging.
    """

    parse_command_line(final=False)

    if options.config:
        configs_to_read = options.config
    else:
        configs_to_read = config_files

    configs_to_read = filter(
        None, [configs_to_read] if not isinstance(configs_to_read, (list, tuple)) else configs_to_read
    )

    for config in configs_to_read:
        parse_config_file(config, final=False)

    # override options from config with command line options
    parse_command_line(final=False)
    MDC.init('master')
    bootstrap_core_logging()
    for config in configs_to_read:
        log.debug('using config: %s', config)
        if options.autoreload:
            tornado.autoreload.watch(config)


async def _init_app(app: FrontikApplication, ioloop: BaseAsyncIOLoop, need_to_register_in_service_discovery):
    initialization_futures = app.init_async()
    await asyncio.gather(*[future for future in initialization_futures if future])
    await run_server(app, ioloop, need_to_register_in_service_discovery)
    if need_to_register_in_service_discovery:
        await app.service_discovery_client.register_service()
    log.info('Successfully inited application')


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


def wrap_handle_with_time_logging(handle: Type[asyncio.Handle], app: FrontikApplication, slow_tasks_logger):
    old_run = handle._run

    def run(self):
        start_time = self._loop.time()
        old_run(self)
        delta = self._loop.time() - start_time
        if delta >= options.asyncio_task_threshold_sec:
            slow_tasks_logger.warning('%s took %.2fms', self, delta * 1000)
        if options.asyncio_task_critical_threshold_sec and delta >= options.asyncio_task_critical_threshold_sec:
            request = get_request() or HTTPServerRequest('GET', '/asyncio_long_task_stub')
            sentry_logger = app.get_sentry_logger(request)
            sentry_logger.update_user_info(ip='127.0.0.1')

            if sentry_logger:
                slow_tasks_logger.warning('no sentry logger available')
                sentry_logger.capture_message(f'{self} took {(delta * 1000):.2f} ms', stack=True)

    asyncio.Handle._run = run
