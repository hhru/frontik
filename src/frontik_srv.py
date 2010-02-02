#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import os.path

import tornado.options
from tornado.options import options

import tornado_util.server

import logging
log = logging.getLogger('frontik')

if __name__ == '__main__':
    dev_config = os.path.join(os.path.dirname(__file__), 'frontik_dev.cfg')

    if os.path.exists(dev_config):
        config = dev_config
    else:
        config = '/etc/frontik/frontik.cfg'

    tornado.options.define('document_roots', None, dict)
    tornado.options.define('suppressed_loggers', ['tornado.httpclient'], list)
    tornado_util.server.bootstrap(config)

    for app, path in options.document_roots.iteritems():
        options.document_roots[app] = os.path.abspath(path)
    
    for log_channel_name in options.suppressed_loggers:
        logging.getLogger(log_channel_name).setLevel(logging.WARN)

    import frontik.app
    tornado_util.server.main(frontik.app.get_app(options=options))

