import tornado.web
import logging

log = logging.getLogger('frontik.server')        

import handler

class StatusHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('pages served: %s\n' % (handler.stats.page_count,))
        self.write('http reqs made: %s\n' % (handler.stats.http_reqs_count,))

def pages_dispatcher(application, request):
    log.info('requested url: %s', request.uri)
    
    page_module_name = 'frontik_www.pages.' + request.path.strip('/').replace('/', '.')
    
    try:
        page_module = __import__(page_module_name, fromlist=['Page'])
        log.debug('using %s from %s', page_module_name, page_module.__file__)
    except ImportError:
        log.exception('%s module not found', page_module_name)
        return tornado.web.ErrorHandler(application, request, 404)
    except:
        log.exception('error while importing %s module', page_module_name)
        return tornado.web.ErrorHandler(application, request, 500)
    
    try:
        return page_module.Page(application, request)
    except:
        log.exception('%s.Page class not found', page_module_name)
        return tornado.web.ErrorHandler(application, request, 500) 

def get_app():
    return tornado.web.Application([
            (r'/status/', StatusHandler),
            (r'.*', pages_dispatcher),
            ])

