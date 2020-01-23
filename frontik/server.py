import asyncio
import errno
import gc
import importlib
import logging
import os.path
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Type

import tornado.autoreload
import tornado.httpserver
import tornado.ioloop
from tornado.httputil import HTTPServerRequest
from tornado.options import parse_command_line, parse_config_file
from tornado.platform.asyncio import BaseAsyncIOLoop
from tornado.util import errno_from_exception

from frontik import service_discovery
from frontik.app import FrontikApplication
from frontik.loggers import bootstrap_logger, bootstrap_core_logging
from frontik.options import options
from frontik.request_context import get_request

log = logging.getLogger('server')


def main(config_file=None):
    parse_configs(config_files=config_file)

    if options.app is None:
        log.exception('no frontik application present (`app` option is not specified)')
        sys.exit(1)

    log.info('starting application %s', options.app)

    try:
        module = importlib.import_module(options.app)
    except Exception as e:
        log.exception('failed to import application module "%s": %s', options.app, e)
        sys.exit(1)

    if options.app_class is not None and not hasattr(module, options.app_class):
        log.exception('application class "%s" not found', options.app_class)
        sys.exit(1)

    application = getattr(module, options.app_class) if options.app_class is not None else FrontikApplication

    try:
        app = application(app_root=os.path.dirname(module.__file__), **options.as_dict())
        app.service_discovery_client = service_discovery.ServiceDiscovery(options)

        gc.disable()
        gc.collect()
        gc.freeze()

        if options.workers != 1:
            fork_processes(app, options.workers)

        gc.enable()

        ioloop = tornado.ioloop.IOLoop.current()

        executor = ThreadPoolExecutor(options.common_executor_pool_size)
        ioloop.asyncio_loop.set_default_executor(executor)
        initialize_application_task = ioloop.asyncio_loop.create_task(_init_app(app, ioloop))

        def initialize_application_task_result_handler(future):
            if future.exception():
                ioloop.stop()
        initialize_application_task.add_done_callback(initialize_application_task_result_handler)
        ioloop.start()
        # to raise init exception if any
        initialize_application_task.result()
    except Exception as e:
        log.exception('frontik application exited with exception: %s', e)
        sys.exit(1)


def fork_processes(app, num_processes):
    log.info("starting %d processes", num_processes)
    children = {}

    def start_child(i):
        pid = os.fork()
        if pid == 0:
            # we are child process - just return
            return i
        else:
            children[pid] = i
            return None

    for i in range(num_processes):
        id = start_child(i)
        if id is not None:
            # we are child process - just return
            return id

    # parent process code
    gc.enable()
    ioloop = tornado.ioloop.IOLoop.current()

    def sigterm_handler(signum, frame):
        log.info('received SIGTERM')
        deregistration = app.service_discovery_client.deregister_service()
        deregistration_with_timeout = asyncio.wait_for(deregistration, timeout=options.stop_timeout)
        deregistration_future = ioloop.asyncio_loop.create_task(deregistration_with_timeout)

        def handle_deregistration_results(future):
            if future.exception() is not None:
                log.error('failed to initialize application, init_async returned: %s', future.exception())
        deregistration_future.add_done_callback(handle_deregistration_results)
        for pid, id in children.items():
            log.info('sending SIGTERM to child %d (pid %d)', id, pid)
            os.kill(pid, signal.SIGTERM)
    signal.signal(signal.SIGTERM, sigterm_handler)

    service_registration = app.service_discovery_client.register_service()
    ioloop.asyncio_loop.run_until_complete(service_registration)
    while children:
        try:
            pid, status = os.wait()
        except OSError as e:
            if errno_from_exception(e) == errno.EINTR:
                continue
            raise

        if pid not in children:
            continue

        id = children.pop(pid)
        if os.WIFSIGNALED(status):
            log.warning("child %d (pid %d) killed by signal %d, restarting", id, pid, os.WTERMSIG(status))
        elif os.WEXITSTATUS(status) != 0:
            log.warning("child %d (pid %d) exited with status %d, restarting", id, pid, os.WEXITSTATUS(status))
        else:
            log.info("child %d (pid %d) exited normally", id, pid)
            continue

        new_id = start_child(id)
        if new_id is not None:
            return new_id

    log.info('all children terminated, exiting')
    sys.exit(0)


async def run_server(app: FrontikApplication, ioloop: BaseAsyncIOLoop):
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
        ioloop.asyncio_loop.create_task(deinit_app(app, ioloop))
        http_server.stop()

        if ioloop_is_running():
            log.info('going down in %s seconds', options.stop_timeout)

            def ioloop_stop():
                if ioloop_is_running():
                    log.info('stopping IOLoop')
                    ioloop.stop()
                    log.info('stopped')

            ioloop.add_timeout(time.time() + options.stop_timeout, ioloop_stop)

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

    bootstrap_core_logging()

    for config in configs_to_read:
        log.debug('using config: %s', config)
        if options.autoreload:
            tornado.autoreload.watch(config)


async def _init_app(app: FrontikApplication, ioloop: BaseAsyncIOLoop):
    initialization_futures = app.init_async()
    if initialization_futures is None:
        log.info('No init futures from app')
        initialization_futures = []
    initialization_futures.append(run_server(app, ioloop))
    if options.workers == 1:
        initialization_futures.append(app.service_discovery_client.register_service())
    await asyncio.gather(*[future for future in initialization_futures if future])


async def deinit_app(app: FrontikApplication, ioloop: BaseAsyncIOLoop):
    if options.workers == 1:
        deregistration = app.service_discovery_client.deregister_service()
        deinit_futures = [asyncio.wait_for(deregistration, timeout=options.stop_timeout)]
    else:
        deinit_futures = []
    deinit_futures.extend([integration.deinitialize_app(app) for integration in app.available_integrations])
    if deinit_futures:
        try:
            await asyncio.gather(*[future for future in deinit_futures if future], loop=ioloop.asyncio_loop)
        except Exception as e:
            log.error('failed to deinit, deinit returned: %s', e)


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
