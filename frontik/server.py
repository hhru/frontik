#!/usr/bin/python
# coding=utf-8

import logging
import os
import sys

import tornado_util.server
from tornado.options import options

import frontik.app
import frontik.options
from frontik.frontik_logging import bootstrap_logging

log = logging.getLogger('frontik.server')


def main(config_file='/etc/frontik/frontik.cfg', app=None):
    tornado_util.server.bootstrap(config_file=config_file, options_callback=bootstrap_logging)

    try:
        if app is None:
            app = options.app

        if app is not None:
            app_name = os.path.basename(os.path.normpath(app))
            options.urls.append((options.app_root_url, frontik.app.App(app_name, app)))

        tornado_app = frontik.app.get_app(options.urls, options.tornado_settings)
    except:
        log.exception('failed to initialize frontik application, quitting')
        sys.exit(1)

    tornado_util.server.main(tornado_app)
