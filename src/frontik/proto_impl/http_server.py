import logging
import paste.httpserver

log = logging.getLogger('frontik.server')

def server_main(config, app):
    host=config.get('server', 'host')
    port=config.getint('server', 'port')
    log.debug('binding to %s:%s', host, port)
        
    paste.httpserver.serve(app, host=host, port=port)
