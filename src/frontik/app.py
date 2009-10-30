import webob.exc
import logging

log = logging.getLogger('frontik.server')

class FrontikApp(object):
    def __init__(self):
        pass
    
    def __call__(self, environ, start_response):
        req = webob.Request(environ)
        log.info('requested url: %s', req.url)
        
        page_module_name = 'frontik_www.pages.' + req.path_info.strip('/').replace('/', '.')
        
        try:
            try:
                page_module = __import__(page_module_name, fromlist=['get_page'])
                log.debug('using %s from %s', page_module_name, page_module.__file__)
            except:
                raise webob.exc.HTTPNotFound('%s module not found' % (page_module_name,))
            
            try:
                page_handler = page_module.get_page
            except:
                raise webob.exc.HTTPNotFound('%s.get_page method not found' % (page_module_name,))
            
            return page_handler(req)(environ, start_response)
        except webob.exc.HTTPException, e:
            return e(environ, start_response)

