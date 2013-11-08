#!/usr/bin/python
# coding=utf-8

import logging
import sys

import tornado_util.server
from tornado.options import options

import frontik.app
import frontik.options
import frontik.frontik_logging as frontik_logging

log = logging.getLogger('frontik.server')


def main(config_file='/etc/frontik/frontik.cfg'):
    tornado_util.server.bootstrap(config_file=config_file)
    frontik_logging.bootstrap_all_logging()

    try:
        app = frontik.app.get_app(options.urls, options.apps)
    except:
        log.exception('failed to initialize frontik application, quitting')
        sys.exit(1)

    tornado_util.server.main(app)
