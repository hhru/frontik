#!/usr/bin/env python
# coding=utf-8

import logging
import sys
import importlib

import tornado_util.server
from tornado.options import options

import frontik.options
from frontik.app import FrontikApplication
from frontik.frontik_logging import bootstrap_logging

log = logging.getLogger('frontik.server')


def main(config_file=None):
    tornado_util.server.bootstrap(config_file=config_file, options_callback=bootstrap_logging)

    if options.app is None:
        log.exception('no frontik application present (`app` option is not specified)')
        sys.exit(1)

    try:
        module = importlib.import_module(options.app)
    except ImportError as e:
        log.exception('failed to import application module "%s": %s', options.app, e)
        sys.exit(1)

    if options.app_class is not None and not hasattr(module, options.app_class):
        log.exception('application class "%s" not found', options.app_class)
        sys.exit(1)

    application = getattr(module, options.app_class) if options.app_class is not None else FrontikApplication

    try:
        tornado_app = application(**options.as_dict())
    except:
        log.exception('failed to initialize frontik application, quitting')
        sys.exit(1)

    tornado_util.server.main(tornado_app)
