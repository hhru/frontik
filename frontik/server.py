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

log = logging.getLogger('server')


class FrontikServer:
    def __init__(self, config_file=None):
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
        self.app = application(app_root=os.path.dirname(module.__file__), app_module=app_module_name,
                               **{**asdict(options), **asdict(http_client_options)})

    async def run(self):
        try:
            app = self.app
            count_down_lock = multiprocessing.Lock()

            gc.disable()
            gc.collect()
            gc.freeze()
            if options.workers != 1:
                self.need_to_register_in_service_discovery = False
                await fork_workers(partial(self._run_worker, app, count_down_lock, self.need_to_register_in_service_discovery),
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
                self.need_to_register_in_service_discovery = True
                await self._run_worker(app, count_down_lock, self.need_to_register_in_service_discovery, None)
        except Exception as e:
            log.exception('frontik application exited with exception: %s', e)
            sys.exit(1)

    async def _run_worker(self, app, count_down_lock, need_to_init, pipe):
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
        await self._init_app(app, count_down_lock, need_to_init, pipe)
        await asyncio.Event().wait()

    async def _init_app(self, app: FrontikApplication, count_down_lock, need_to_register_in_service_discovery, pipe):
        await app.init()
        loop = asyncio.get_event_loop()
        if not need_to_register_in_service_discovery:
            app.upstream_update_listener = UpstreamUpdateListener(app.upstream_manager, pipe)
        await self._run_server(app, need_to_register_in_service_discovery)
        log.info(f'Successfully inited application {app.app}')
        with count_down_lock:
            app.init_workers_count_down.value -= 1
            log.info(f'worker is up, remaining workers = {app.init_workers_count_down.value}')
        if need_to_register_in_service_discovery:
            register_task = loop.create_task(app.service_discovery_client.register_service())

            def register_task_result_handler(future):
                if future.exception():
                    loop.stop()
                    future.result()

            register_task.add_done_callback(register_task_result_handler)

    async def _run_server(self, app: FrontikApplication, need_to_register_in_service_discovery):
        """Starts Frontik server for an application"""

        log.info('starting server on %s:%s', options.host, options.port)
        self.http_server = tornado.httpserver.HTTPServer(app, xheaders=options.xheaders)
        self.http_server.bind(options.port, options.host, reuse_port=options.reuse_port)
        self.http_server.start()

        loop = asyncio.get_event_loop()

        if options.autoreload:
            tornado.autoreload.start(1000)

        def sigterm_handler(signum, frame):
            log.info('requested shutdown, shutting down server on %s:%d', options.host, options.port)
            try:
                loop.call_soon_threadsafe(self.server_stop)

                if loop.is_running():
                    log.info('going down in %s seconds', options.stop_timeout)

                    def ioloop_stop():
                        if loop.is_running():
                            log.info('stopping IOLoop')
                            loop.stop()
                            log.info('stopped')

                    loop.call_later(options.stop_timeout, ioloop_stop)
            except RuntimeError:
                pass

        signal.signal(signal.SIGTERM, sigterm_handler)
        signal.signal(signal.SIGINT, sigterm_handler)

    async def server_stop(self):
        self.http_server.stop()
        await self._deinit_app(self.app, self.need_to_register_in_service_discovery)

    async def _deinit_app(self, app: FrontikApplication, need_to_register_in_service_discovery):
        if need_to_register_in_service_discovery:
            deregistration = app.service_discovery_client.deregister_service_and_close()
            deinit_futures = [asyncio.wait_for(deregistration, timeout=options.stop_timeout)]
        else:
            deinit_futures = []
        deinit_futures.extend([integration.deinitialize_app(app) for integration in app.available_integrations])
        if deinit_futures:
            try:
                await asyncio.gather(*[future for future in deinit_futures if future])
                log.info('Successfully deinited application')
            except Exception as e:
                log.exception('failed to deinit, deinit returned: %s', e)
