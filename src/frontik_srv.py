#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import os.path
import logging
import ConfigParser

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.autoreload
import tornado.options

from tornado.options import options

import webob

import frontik
import frontik.app

log = logging.getLogger('frontik.server')

app = tornado.web.Application([
    (r'.*', frontik.app.dispatcher),
])

if __name__ == '__main__':
    tornado.options.parse_command_line()
    
    config = ConfigParser.ConfigParser()
    configs = config.read(['/etc/frontik/frontik.ini', './frontik.dev.ini'])
    
    if configs:
        log.debug('read configs: %s', ', '.join(os.path.abspath(i) for i in configs))
    else:
        log.error('failed to find any config file, aborting')
        sys.exit(1)
    
    special_document_dir = os.path.abspath(config.get('server', 'document_dir'))
    if special_document_dir:
        log.debug('appending "%s" document_dir to sys.path', special_document_dir)
        sys.path.append(special_document_dir)
    
    http_server = tornado.httpserver.HTTPServer(app)
    
    port = int(config.get('server', 'port'))
    host = config.get('server', 'host') or '0.0.0.0'
    
    log.info('starting server on %s:%s', host, port)
    http_server.listen(port, host)
    
    io_loop = tornado.ioloop.IOLoop.instance()
    
    tornado.autoreload.start(io_loop, 1)
    io_loop.start()
