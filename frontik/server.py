#!/usr/bin/env python
# coding=utf-8

import logging
import sys

import tornado_util.server
from tornado.options import options

import frontik.app
import frontik.options
from frontik.frontik_logging import bootstrap_logging

log = logging.getLogger('frontik.server')


def main(config_file=None):
    tornado_util.server.bootstrap(config_file=config_file, options_callback=bootstrap_logging)

    try:
        if options.app is None:
            log.exception('no frontik application present (`app` option is not specified)')
            sys.exit(1)

        tornado_app = frontik.app.get_tornado_app(
            options.app_root_url, frontik.app.App(options.app), options.tornado_settings
        )
    except:
        log.exception('failed to initialize frontik application, quitting')
        sys.exit(1)

    tornado_util.server.main(tornado_app)
