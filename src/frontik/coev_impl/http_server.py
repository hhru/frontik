import logging
import coewsgi.httpserver

log = logging.getLogger('frontik.coev.server')

def server_main(config, app):
    host=config.get('server', 'host')
    port=config.getint('server', 'port')
    log.debug('binding to %s:%s', host, port)
    
    import coev
    coev.setdebug(module=True, library=True)
    
    coewsgi.httpserver.serve(app, host=host, port=port)
