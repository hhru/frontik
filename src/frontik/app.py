import tornado.web
import logging

log = logging.getLogger('frontik.server')        

def dispatcher(application, request):
    log.info('requested url: %s', request.uri)
    
    page_module_name = 'frontik_www.pages.' + request.path.strip('/').replace('/', '.')
    
    try:
        page_module = __import__(page_module_name, fromlist=['Page'])
        log.debug('using %s from %s', page_module_name, page_module.__file__)
    except ImportError:
        log.exception('%s module not found', page_module_name)
        return tornado.web.ErrorHandler(application, request, 404)
    
    try:
        return page_module.Page(application, request)
    except:
        log.exception('%s.Page class not found', page_module_name)
        return tornado.web.ErrorHandler(application, request, 404) 
