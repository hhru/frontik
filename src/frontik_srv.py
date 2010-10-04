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

    tornado.options.define('apps', {}, dict)
    tornado.options.define('suppressed_loggers', ['tornado.httpclient'], list)
    tornado.options.define('handlers_count', 100, int)
    tornado.options.define('debug', False, bool)
    tornado.options.define('debug_login', None, str)
    tornado.options.define('debug_password', None, str)

    tornado_util.server.bootstrap(config)

    for log_channel_name in options.suppressed_loggers:
        logging.getLogger(log_channel_name).setLevel(logging.WARN)

    import frontik.app

    try:
        app = frontik.app.get_app(options.apps)
    except:
        log.exception('failed to initialize frontik.app, quitting')
        sys.exit(1)
    
    tornado_util.server.main(app)

