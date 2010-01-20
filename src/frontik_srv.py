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
    tornado_util.server.bootstrap(config)

    if options.document_root:
        special_document_dir = os.path.abspath(options.document_root)
        log.debug('appending "%s" document_dir to sys.path', special_document_dir)
        sys.path.append(special_document_dir)

    try:
        import frontik_www
        import frontik_www.config
    except:
        log.exception('frontik_www module cannot be found')
        sys.exit(1)

    watch_paths = getattr(frontik_www.config, "watch_paths", []).append(config)

    import frontik.app
    tornado_util.server.main(frontik.app.get_app(frontik_www.config), paths=watch_paths)

