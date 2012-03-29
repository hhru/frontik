#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging
import sys

import tornado.options
import tornado_util.server
from tornado.options import options

import frontik.app
import frontik.options

from frontik.util import MaxLenSysLogHandler

log = logging.getLogger("frontik.server")

def bootstrap_all_logging():
    if tornado.options.options.syslog:
        syslog_handler = MaxLenSysLogHandler(
            facility=MaxLenSysLogHandler.facility_names[
                     tornado.options.options.syslog_facility],
            address=tornado.options.options.syslog_address,
            msg_max_length=tornado.options.options.syslog_msg_max_length)
        syslog_handler.setFormatter(
            logging.Formatter(
                "[%(process)s] %(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(syslog_handler)


    if tornado.options.options.graylog:
        try:
            from graypy import GELFHandler
            graylog_handler = GELFHandler(tornado.options.options.graylog_host,
                tornado.options.options.graylog_port, tornado.options.options.graylog_chunk_size, False)

            logging.getLogger().addHandler(graylog_handler)
        except ImportError:
            log.error('Cannot import graypy and start graylog logging!')

    for log_channel_name in options.suppressed_loggers:
        logging.getLogger(log_channel_name).setLevel(logging.WARN)


def main(config_file="/etc/frontik/frontik.cfg"):
    tornado_util.server.bootstrap(config_file=config_file)

    bootstrap_all_logging()

    try:
        app = frontik.app.get_app(options.urls, options.apps)
    except:
        log.exception("failed to initialize frontik.app, quitting")
        sys.exit(1)

    tornado_util.server.main(app)
