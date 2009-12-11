import logging
log = logging.getLogger('frontik.server')

def bootstrap():
    import sys
    import os.path

    import tornado.options
    from tornado.options import options

    tornado.options.define('host', 'localhost', str)
    tornado.options.define('port', 8080, int)
    tornado.options.define('document_root', None, str)
    tornado.options.define('daemonize', True, bool)
    tornado.options.define('autoreload', True, bool)
    tornado.options.define('config', None, str)

    tornado.options.parse_command_line()
    if options.config:
        configs_to_read = [options.config]
    else:
        configs_to_read = ['/etc/frontik/frontik.cfg', 
                           './frontik_dev.cfg']

    configs = tornado.options.parse_config_files(configs_to_read)
    
    tornado.options.parse_command_line()

    if options.daemonize:
        import daemon

        ctx = daemon.DaemonContext()
        ctx.open()

    tornado.options.process_options()

    if configs:
        log.debug('read configs: %s', ', '.join(os.path.abspath(i) for i in configs))
    else:
        sys.stderr.write('failed to find any config file, aborting\n')
        sys.exit(1)

    if options.document_root:
        special_document_dir = os.path.abspath(options.document_root)
        log.debug('appending "%s" document_dir to sys.path', special_document_dir)
        sys.path.append(special_document_dir)

def main(host, port, autoreload):
    import tornado.httpserver
    import tornado.ioloop
    import tornado.web

    import frontik
    import frontik.app

    try:
        import frontik_www
    except ImportError:
        log.error('frontik_www module cannot be found')
        sys.exit(1)

    logging.getLogger('tornado.httpclient').setLevel(logging.WARN)

    try:
        log.info('starting server on %s:%s', host, port)
        http_server = tornado.httpserver.HTTPServer(frontik.app.get_app())
        http_server.listen(port, host)
    
        io_loop = tornado.ioloop.IOLoop.instance()
    
        if autoreload:
            import tornado.autoreload
            tornado.autoreload.start(io_loop, 1000)

        io_loop.start()
    except Exception, e:
        log.exception('main failed')

