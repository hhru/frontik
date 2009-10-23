# -*- coding: utf-8 -*-

# прототип hhscript'а без использования coev-python

import logging
import webob.exc

log = logging.getLogger('frontik')

class HHScriptApp(object):
    def __init__(self):
        pass
    
    def __call__(self, environ, start_response):
        req = webob.Request(environ)
        log.info('requested url: %s', req.url)
        
        page_module_name = 'hh.pages.' + req.path_info.strip('/').replace('/', '.')
        
        try:
            try:
                page_module = __import__(page_module_name, fromlist=['get_page'])
            except:
                raise webob.exc.HTTPNotFound('%s module not found' % (page_module_name,))
            
            try:
                page_handler = page_module.get_page
            except:
                raise webob.exc.HTTPNotFound('%s.get_page method not found' % (page_module_name,))
            
            return page_handler(req)(environ, start_response)
        except webob.exc.HTTPException, e:
            return e(environ, start_response)

if __name__ == '__main__':
    import sys
    
    app = HHScriptApp()

    logging.basicConfig(level=logging.DEBUG)
        
    if len(sys.argv) > 1:
        request = webob.Request.blank(sys.argv[1])
        print ''.join(app(request.environ, lambda *args, **kw: None))
    
    else:
        from wsgiref.simple_server import make_server
        httpd = make_server('localhost', 8080, app)
        httpd.serve_forever()