#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import os.path
import logging
import ConfigParser

import webob

import frontik
import frontik.app

log = logging.getLogger('frontik.server')

if __name__ == '__main__':
    app = frontik.app.FrontikApp()

    logging.basicConfig(level=logging.DEBUG)
    
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
    
    if len(sys.argv) > 1:
        request = webob.Request.blank(sys.argv[1])
        print ''.join(app(request.environ, lambda *args, **kw: None))
    
    else:
        frontik.server_main(config, app)
