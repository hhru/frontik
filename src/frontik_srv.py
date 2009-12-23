#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import os.path

import frontik.app

import tornado.options
from tornado.options import options

import tornado_util.server

import logging
log = logging.getLogger('frontik')

if __name__ == '__main__':
    if os.path.exists('.svn'):
        config = './frontik_dev.cfg'
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
    except ImportError:
        log.error('frontik_www module cannot be found')
        sys.exit(1)

    for log_channel_name in [
        #'tornado.httpclient'
        ]:
        logging.getLogger(log_channel_name).setLevel(logging.WARN)

    tornado_util.server.main(frontik.app.get_app())

