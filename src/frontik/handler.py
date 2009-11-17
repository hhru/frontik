from frontik import etree

from frontik.doc import Doc

import logging
log = logging.getLogger('frontik.page_handler')

import tornado.web
import tornado.httpclient

from functools import partial

import future
http_client = tornado.httpclient.AsyncHTTPClient(max_clients=50)

class ResponsePlaceholder(future.FutureVal):
    def __init__(self, request):
        self.request = request
        self.data = None

    def set_response(self, handler, response):
        if response.code == 200:
            self.data = etree.fromstring(response.body)
        else:
            handler.log.warn('%s failed %s', response.code, response.effective_url)
            self.data = etree.Element('error', dict(url=response.effective_url))
    
    def get(self):
        return self.data

class PageHandler(tornado.web.RequestHandler):
    current_request_id = 0
    
    def __init__(self, *args, **kw):
        tornado.web.RequestHandler.__init__(self, *args, **kw)
        
        self.doc = Doc()
        self.n_waiting_reqs = 0
        self.finishing = False
        
        self.request_id = self.request.headers.get('X-Request-Id', 
                                                   self.get_next_request_id())
        
        self.log = logging.getLogger('frontik.page_handler.%s' % (self.request_id,))
        
        self.log.debug('started')
    
    @classmethod
    def get_next_request_id(cls):
        cls.current_request_id += 1
        return cls.current_request_id
    
    def finish_page(self):
        self.log.debug('going to finish')
        
        self.finishing = True
        self._try_finish_page()
    
    def _try_finish_page(self):
        if self.finishing and self.n_waiting_reqs == 0:
            self._real_finish()
    
    def _real_finish(self):
        self.log.debug('finishing')
        chunks = list(self.doc._finalize_data())
        
        self.set_header('Content-Type', 'application/xml')
        self.write('<?xml version="1.0" ?>\n')
        
        for chunk in chunks:
            self.write(str(chunk))
        
        self.log.debug('done')
        self.finish('')
    
    def fetch_url(self, req):
        placeholder = ResponsePlaceholder(req)
        self.n_waiting_reqs += 1
        
        http_client.fetch(req, self.async_callback(partial(self._fetch_url_response, placeholder)))
        
        return placeholder
        
    def _fetch_url_response(self, placeholder, response):
        self.n_waiting_reqs -= 1

        self.log.debug('got %s %s in %s, %s requests pending', response.code, response.effective_url, response.request_time, self.n_waiting_reqs)
        
        placeholder.set_response(self, response)
        
        self._try_finish_page()