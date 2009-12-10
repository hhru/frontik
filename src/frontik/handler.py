# -*- coding: utf-8 -*-

import os.path

from functools import partial

import tornado.web
import tornado.httpclient
import tornado.options

from frontik import etree
from frontik.doc import Doc

import frontik_www

import logging
log = logging.getLogger('frontik.handler')

import future
http_client = tornado.httpclient.AsyncHTTPClient(max_clients=200, 
                                                 max_simultaneous_connections=200)

class ResponsePlaceholder(future.FutureVal):
    def __init__(self):
        pass

    def set_response(self, handler, response):
        if not response.error:
            self.has_response = True
            self.response = response
        else:
            handler.log.warn('%s failed %s', response.code, 
                             response.effective_url)
            self.has_response = False
            self.data = etree.Element('error', dict(url=response.effective_url))
    
    def get(self):
        if self.has_response:
            return [etree.Comment(self.response.effective_url),
                    etree.fromstring(self.response.body)]
        else:
            return self.data

class Stats:
    def __init__(self):
        self.page_count = 0
        self.http_reqs_count = 0

stats = Stats()

class PageHandler(tornado.web.RequestHandler):
    def __init__(self, *args, **kw):
        tornado.web.RequestHandler.__init__(self, *args, **kw)
        
        self.doc = Doc()
        self.n_waiting_reqs = 0
        self.finishing = False
        
        self.request_id = self.request.headers.get('X-Request-Id', 
                                                   self.get_next_request_id())
        
        self.log = logging.getLogger('frontik.handler.%s' % (self.request_id,))
        
        self.log.debug('started %s %s', self.request.method, self.request.uri)
    
    @classmethod
    def get_next_request_id(cls):
        stats.page_count += 1
        return stats.page_count
    
    def fetch_url(self, url):
        placeholder = ResponsePlaceholder()
        self.n_waiting_reqs += 1
        stats.http_reqs_count += 1
        
        http_client.fetch(
            tornado.httpclient.HTTPRequest(
                url=url,
                headers={
                    'Connection':'Keep-Alive',
                    'Keep-Alive':'1000'}), 
            self.async_callback(partial(self._fetch_url_response, placeholder)))
        
        return placeholder
        
    def _fetch_url_response(self, placeholder, response):
        self.n_waiting_reqs -= 1

        self.log.debug('got %s %s in %.3f, %s requests pending', response.code, response.effective_url, response.request_time, self.n_waiting_reqs)
        
        placeholder.set_response(self, response)
        
        self._try_finish_page()

    def finish_page(self):
        self.log.debug('going to finish')
        
        self.finishing = True
        self._try_finish_page()
    
    def _try_finish_page(self):
        if self.finishing and self.n_waiting_reqs == 0:
            self._real_finish()
    
    def _real_finish(self):
        self.log.debug('finishing')

        self.set_header('Content-Type', 'application/xml')
        self.write(self.doc.to_string())

        self.log.debug('done')

        self.finish('')
    
    ### 

    # глобальный кеш
    xml_files_cache = dict()

    def xml_from_file(self, filename):
        if filename in self.xml_files_cache:
            self.log.debug('got %s file from cache', filename)
            return self.xml_files_cache[filename]
        else:
            ret = self._xml_from_file(filename)
            self.xml_files_cache[filename] = ret
            return ret

    frontik_www_dir = os.path.dirname(frontik_www.__file__)

    def _xml_from_file(self, filename):
        real_filename = os.path.join(self.frontik_www_dir, filename)

        self.log.debug('read %s file from %s', filename, real_filename)

        if os.path.exists(real_filename):
            try:
                return etree.parse(file(real_filename)).getroot()
            except:
                return etree.Element('error', dict(msg='failed to parse file: %s' % (filename,)))
        else:
            return etree.Element('error', dict(msg='file not found: %s' % (filename,)))
            
