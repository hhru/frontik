# -*- coding: utf-8 -*-

# frontik реализует следующий внешний API

# etree - модуль, который используется как реализация ElementTree
import xml.etree.ElementTree as etree

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
http_client = tornado.httpclient.AsyncHTTPClient()

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
    def __init__(self, *args, **kw):
        tornado.web.RequestHandler.__init__(self, *args, **kw)
        
        self.doc = Doc()
        self.n_waiting_reqs = 0
        self.finishing = False
    
    def finish(self, data=None):
        self.finishing = True
        self._try_finish()
    
    def _try_finish(self):
        if self.finishing:
            if self.n_waiting_reqs == 0:
                log.debug('finishing')
                self._real_finish()
            else:
                log.debug('cannot finish now, %s requests pending', self.n_waiting_reqs)
    
    def _real_finish(self):
        chunks = list(self.doc._finalize_data())
        
        self.set_header('Content-Type', 'application/xml')
        self.write('<?xml version="1.0" ?>\n')
        
        for chunk in chunks:
            self.write(str(chunk))
        
        tornado.web.RequestHandler.finish(self, '')
    
    def fetch_url(self, req):
        placeholder = ResponsePlaceholder(req)
        self.n_waiting_reqs += 1
        
        http_client.fetch(req, self.async_callback(partial(self._fetch_url_response, placeholder)))
        
        return placeholder
        
    def _fetch_url_response(self, placeholder, response):
        self.n_waiting_reqs -= 1
        
        placeholder.set_response(response)
        
        self._try_finish()