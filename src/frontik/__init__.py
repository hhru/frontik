# -*- coding: utf-8 -*-

# frontik реализует следующий внешний API

# etree - модуль, который используется как реализация ElementTree
#import xml.etree.ElementTree as etree
import lxml.etree as etree

# Doc, DocResponse классы для формирования XML-ответа
from doc import Doc
from util import make_url

# реализация сервера
from proto_impl.http_client import http_get
from proto_impl.http_server import server_main

#from proto_impl.http_client import http_get
#from coev_impl.http_server import server_main

import logging
log = logging.getLogger('frontik')

import tornado.web
import tornado.httpclient

from functools import partial

import future
http_client = tornado.httpclient.AsyncHTTPClient(max_clients=50)

class ResponsePlaceholder(future.FutureVal):
    def __init__(self, request):
        self.request = request
        self.data = None

    def set_response(self, response):
        if response.code == 200:
            self.data = etree.fromstring(response.body)
        else:
            log.warn('%s failed %s', response.code, response.effective_url)
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
        
        self.request_id = self.get_next_request_id()
        self.log = logging.getLogger('frontik.page_handler.%i' % (self.request_id,))
    
    @classmethod
    def get_next_request_id(cls):
        cls.current_request_id += 1
        return cls.current_request_id
    
    def finish(self, data=None):
        self.log.debug('going to finish')
        
        self.finishing = True
        self._try_finish()
    
    def _try_finish(self):
        if self.finishing and self.n_waiting_reqs == 0:
            self._real_finish()
    
    def _real_finish(self):
        self.log.debug('finishing')
        chunks = list(self.doc._finalize_data())
        
        self.set_header('Content-Type', 'application/xml')
        self.write('<?xml version="1.0" ?>\n')
        
        for chunk in chunks:
            self.write(str(chunk))
        
        tornado.web.RequestHandler.finish(self, '')
        self.log.debug('done')
    
    def fetch_url(self, req):
        placeholder = ResponsePlaceholder(req)
        self.n_waiting_reqs += 1
        
        http_client.fetch(req, self.async_callback(partial(self._fetch_url_response, placeholder)))
        
        return placeholder
        
    def _fetch_url_response(self, placeholder, response):
        self.n_waiting_reqs -= 1

        self.log.debug('got %s %s in %s, %s requests pending', response.code, response.effective_url, response.request_time, self.n_waiting_reqs)
        
        placeholder.set_response(response)
        
        self._try_finish()