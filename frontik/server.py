#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging
import sys

import tornado.options
import tornado_util.server
from tornado.options import options

import frontik.app
import frontik.options

from frontik.util import SysLogHandler

log = logging.getLogger("frontik.server")

def main(config_file="/etc/frontik/frontik.cfg"):
    tornado_util.server.bootstrap(config_file=config_file)

    if tornado.options.options.syslog:
        syslog_handler =SysLogHandler(
            facility=SysLogHandler.facility_names[tornado.options.options.syslog_facility],
            address=tornado.options.options.syslog_address,
            msg_max_length=tornado.options.options.syslog_msg_max_length)
        syslog_handler.setFormatter(
            logging.Formatter("[%(process)s] %(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(syslog_handler)

    for log_channel_name in options.suppressed_loggers:
        logging.getLogger(log_channel_name).setLevel(logging.WARN)

    try:
        app = frontik.app.get_app(options.urls, options.apps)
    except:
        log.exception("failed to initialize frontik.app, quitting")
        sys.exit(1)

    tornado_util.server.main(app)
