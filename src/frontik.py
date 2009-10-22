# -*- coding: utf-8 -*-

# прототип hhscript'а без использования coev-python

import logging
import webob.exc

import hh.pages

log = logging.getLogger('frontik')

class HHScriptApp(object):
    def __init__(self):
        pass
    
    def __call__(self, environ, start_response):
        req = webob.Request(environ)
        
        page_name = req.path_info.strip('/')
        
        log.info('requested url: %s', req.url)
        
        if hasattr(hh.pages, page_name):
            page_handler = getattr(hh.pages, page_name)
            try:
                return page_handler(req)(environ, start_response)
            except webob.exc.HTTPException, e:
                return e(environ, start_response)
        
        else:
            return webob.exc.HTTPNotFound('%s not found' % (page_name,))(environ, start_response)

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