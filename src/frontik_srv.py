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

    tornado.options.define('document_root', None, str)
    tornado.options.define('suppressed_loggers', ['tornado.httpclient'], list)

    tornado_util.server.bootstrap(config)

    if options.document_root:
        abs_document_root = os.path.abspath(options.document_root)
        log.debug('appending "%s" document_dir to sys.path', abs_document_root)
        sys.path.insert(0, abs_document_root)

    try:
        import frontik_www
        import frontik_www.config

    except:
        log.exception('frontik_www module cannot be found')
        sys.exit(1)

    if options.document_root:
        if not frontik_www.__file__.startswith(abs_document_root):
            log.error('frontik_www module is found at %s when %s expected', 
                      frontik_www.__file__,
                      abs_document_root)
            sys.exit(1)

    watch_paths = getattr(frontik_www.config, "watch_paths", [])
    watch_paths.append(config)

    for log_channel_name in options.suppressed_loggers:
        logging.getLogger(log_channel_name).setLevel(logging.WARN)

    import frontik.app
    tornado_util.server.main(frontik.app.get_app(frontik_www.config), watch_paths=watch_paths)

