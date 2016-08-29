# coding=utf-8

import importlib
import logging
import os
import signal
import sys
import time
import traceback

import tornado.autoreload
import tornado.httpserver
import tornado.ioloop
import tornado.options
from tornado.options import options

from frontik.app import FrontikApplication
from frontik.loggers import bootstrap_core_logging

log = logging.getLogger('frontik.server')


def parse_configs_and_start(config_files):
    """
    — read command line options and config file
    — daemonize
    """

    tornado.options.parse_command_line(final=False)

    if options.config:
        configs_to_read = options.config
    else:
        configs_to_read = config_files

    configs_to_read = filter(
        None, [configs_to_read] if not isinstance(configs_to_read, (list, tuple)) else configs_to_read
    )

    for config in configs_to_read:
        tornado.options.parse_config_file(config, final=False)

    # override options from config with command line options
    tornado.options.parse_command_line(final=False)

    if options.daemonize:
        import daemon
        ctx = daemon.DaemonContext()
        ctx.initgroups = False  # For python-daemon >= 2
        ctx.open()

    if options.pidfile:
        with open(options.pidfile, 'w+') as pidfile:
            pidfile.write(str(os.getpid()))

    bootstrap_core_logging()

    for config in configs_to_read:
        log.debug('using config: %s', config)
        tornado.autoreload.watch(config)


def run_server(app):
    """
    — run server on host:port
    — launch autoreload on file changes
    """

    def ioloop_is_running():
        return tornado.ioloop.IOLoop.instance()._running

    try:
        log.info('starting server on %s:%s', options.host, options.port)
        http_server = tornado.httpserver.HTTPServer(app)
        http_server.listen(options.port, options.host)

        io_loop = tornado.ioloop.IOLoop.instance()

        if options.autoreload:
            tornado.autoreload.start(io_loop, 1000)

        def log_ioloop_block(signum, frame):
            io_loop.add_callback_from_signal(
                log.warning, 'IOLoop blocked for %f seconds in\n%s',
                io_loop._blocking_signal_threshold, ''.join(traceback.format_stack(frame))
            )

        def sigterm_handler(signum, frame):
            log.info('requested shutdown')
            log.info('shutting down server on %s:%d', options.host, options.port)
            io_loop.add_callback_from_signal(server_stop)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)

        def server_stop():
            http_server.stop()

            if ioloop_is_running():
                log.info('going down in %s seconds', options.stop_timeout)

                def ioloop_stop():
                    if ioloop_is_running():
                        log.info('stopping IOLoop')
                        tornado.ioloop.IOLoop.instance().stop()
                        log.info('stopped')

                tornado.ioloop.IOLoop.instance().add_timeout(time.time() + options.stop_timeout, ioloop_stop)

        if tornado.options.options.log_blocked_ioloop_timeout > 0:
            io_loop.set_blocking_signal_threshold(tornado.options.options.log_blocked_ioloop_timeout, log_ioloop_block)

        signal.signal(signal.SIGTERM, sigterm_handler)
    except Exception:
        log.exception('failed to start Tornado application')


def main(config_file=None):
    # noinspection PyUnresolvedReferences
    import frontik.options

    parse_configs_and_start(config_files=config_file)

    if options.app is None:
        log.exception('no frontik application present (`app` option is not specified)')
        sys.exit(1)

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
        tornado_app = application(**options.as_dict())
        ioloop = tornado.ioloop.IOLoop.instance()

        def _async_init_cb():
            def _run_server_cb(future):
                if future.exception() is not None:
                    log.exception('failed to start: %s', future.exception())
                    sys.exit(1)

                run_server(tornado_app)

            ioloop.add_future(
                tornado_app.init_async(), _run_server_cb
            )

        ioloop.add_callback(_async_init_cb)
        ioloop.start()
    except:
        log.exception('failed to initialize frontik application, quitting')
        sys.exit(1)
