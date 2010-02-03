import logging
log = logging.getLogger('frontik.server')

import tornado.options
from tornado.options import options

def bootstrap(config_file):
    '''
    - объявить стандартные опции config, host, port, daemonize, autoreload
    - прочитать командную строку, конфигурационный файл
    - демонизироваться
    - инициализировать протоколирование
    '''

    import sys
    import os.path

    tornado.options.define('config', None, str)

    tornado.options.define('host', '0.0.0.0', str)
    tornado.options.define('port', 8080, int)
    tornado.options.define('daemonize', True, bool)
    tornado.options.define('autoreload', True, bool)

    tornado.options.parse_command_line()
    if options.config:
        configs_to_read = [options.config]
    else:
        configs_to_read = [config_file]

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

def main(app):
    '''
    - запустить веб-сервер на указанных в параметрах host:port
    - запустить автоперезагрузку сервера, при изменении исходников
    '''

    import tornado.httpserver
    import tornado.ioloop
    import tornado.web

    try:
        import frontik_www
    except ImportError:
        log.error('frontik_www module cannot be found')
        sys.exit(1)

    logging.getLogger('tornado.httpclient').setLevel(logging.WARN)

    try:
        log.info('starting server on %s:%s', options.host, options.port)
        http_server = tornado.httpserver.HTTPServer(app)
        http_server.listen(options.port, options.host)
    
        io_loop = tornado.ioloop.IOLoop.instance()
    
        if options.autoreload:
            import tornado.autoreload
            tornado.autoreload.start(io_loop, 1000)

        io_loop.start()
    except Exception, e:
        log.exception('main failed')

