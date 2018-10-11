import importlib
import logging
import os.path
import signal
import sys
import time

import tornado.autoreload
import tornado.httpserver
import tornado.ioloop
from tornado.options import parse_command_line, parse_config_file

from frontik.app import FrontikApplication
from frontik.loggers import bootstrap_logger, bootstrap_core_logging
from frontik.options import options

log = logging.getLogger('server')


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


def run_server(app: FrontikApplication):
    """Starts Frontik server for an application"""

    try:
        if options.asyncio_task_threshold_sec is not None:
            slow_tasks_logger = bootstrap_logger('slow_tasks', logging.WARNING, use_json_formatter=False)

            import asyncio
            import reprlib

            reprlib.aRepr.maxother = 128
            old_run = asyncio.Handle._run

            def run(self):
                start_time = self._loop.time()
                old_run(self)
                delta = self._loop.time() - start_time
                if delta >= options.asyncio_task_threshold_sec:
                    slow_tasks_logger.warning('%s took %.2fms', self, delta * 1000)

            asyncio.Handle._run = run

        log.info('starting server on %s:%s', options.host, options.port)
        http_server = tornado.httpserver.HTTPServer(app, xheaders=options.xheaders)
        http_server.bind(options.port, options.host, reuse_port=options.reuse_port)
        http_server.start()

        io_loop = tornado.ioloop.IOLoop.current()

        if options.autoreload:
            tornado.autoreload.start(1000)

        def sigterm_handler(signum, frame):
            log.info('requested shutdown')
            log.info('shutting down server on %s:%d', options.host, options.port)
            io_loop.add_callback_from_signal(server_stop)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)

        def ioloop_is_running():
            return io_loop.asyncio_loop.is_running()

        def server_stop():
            http_server.stop()

            if ioloop_is_running():
                log.info('going down in %s seconds', options.stop_timeout)

                def ioloop_stop():
                    if ioloop_is_running():
                        log.info('stopping IOLoop')
                        io_loop.stop()
                        log.info('stopped')

                io_loop.add_timeout(time.time() + options.stop_timeout, ioloop_stop)

        signal.signal(signal.SIGTERM, sigterm_handler)
    except Exception:
        log.exception('failed to start Tornado application')
        sys.exit(1)


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
        tornado_app = application(app_root=os.path.dirname(module.__file__), **options.as_dict())
        ioloop = tornado.ioloop.IOLoop.current()

        def _async_init_cb():
            try:
                init_futures = list(tornado_app.init_async())

                def await_features(future):
                    if future.exception() is not None:
                        log.error('failed to initialize application, init_async returned: %s', future.exception())
                        sys.exit(1)

                    init_futures.pop()
                    if not init_futures:
                        run_server(tornado_app)

                for future in init_futures:
                    ioloop.add_future(future, await_features)
            except Exception:
                log.exception('failed to initialize application')
                sys.exit(1)

        ioloop.add_callback(_async_init_cb)
        ioloop.start()
    except BaseException:
        log.exception('frontik application exited with exception')
        sys.exit(1)
