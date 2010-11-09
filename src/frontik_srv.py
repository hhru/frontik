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

    tornado.options.define('syslog_address', "/dev/log", str)
    tornado.options.define('syslog', False, bool)

    tornado.options.define('xml_debug', False, bool)
    tornado.options.define('debug', False, bool)
    tornado.options.define('debug_login', None, str)
    tornado.options.define('debug_password', None, str)
    tornado.options.define('debug_xsl', '/usr/lib/frontik/debug.xsl', str)

    tornado.options.define('executor_pool', False, bool)
    tornado.options.define('executor_pool_size', 7, int)

    tornado_util.server.bootstrap(config)

    if tornado.options.options.syslog:
        syslog_handler = logging.handlers.SysLogHandler(facility = logging.handlers.SysLogHandler.LOG_DEBUG, address = tornado.options.options.syslog_address)
        syslog_handler.setFormatter(logging.Formatter('[%(asctime)s %(name)s] %(levelname)s %(message)s'))
        log.addHandler(syslog_handler)

    for log_channel_name in options.suppressed_loggers:
        logging.getLogger(log_channel_name).setLevel(logging.WARN)

    import frontik.app

    try:
        app = frontik.app.get_app(options.apps)
    except:
        log.exception('failed to initialize frontik.app, quitting')
        sys.exit(1)

    tornado_util.server.main(app)
