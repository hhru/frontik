# -*- coding: utf-8 -*-

import webob
import urllib2
import logging
import pycurl
import threading
import cStringIO
import time

import coev

from frontik import etree as et
import frontik.future

log = logging.getLogger('frontik.coev.http_client')

# copy/paste from tornado.httpclient
def _curl_create(max_simultaneous_connections=None):
    curl = pycurl.Curl()
    #if logging.getLogger().isEnabledFor(logging.DEBUG):
    #    curl.setopt(pycurl.VERBOSE, 1)
    #    curl.setopt(pycurl.DEBUGFUNCTION, _curl_debug)
    curl.setopt(pycurl.MAXCONNECTS, max_simultaneous_connections or 5)
    return curl

class HTTPClient(object):
    def __init__(self):
        self._clients = [_curl_create(5) for i in range(5)]
        self._multi = pycurl.CurlMulti()
        self._reqs = list()
        
        self.client_loop_thread = threading.Thread(target=self.client_loop)
        self.client_loop_thread.start()
    
    # runs in client
    def fetch(self, req):
        self._reqs.append((req, coev.current()))
        return coev.switch2scheduler()

    def pop_requests(self):
        res = self._reqs
        self._reqs = list()
        
        return res

    # runs in server thread
    def client_loop(self):
        while True:
            while True:
                ret, num_handles = self._multi.perform()
                if ret != pycurl.E_CALL_MULTI_PERFORM:
                    break

            while True:
                num_q, ok_list, err_list = self._multi.info_read()
                for curl in ok_list:
                    #self._finish(curl)
                    # XXX это не будет работать, потому что управление не возвращается в client_loop
                    coev.switch(curl.info['thread_id'], curl.info['buffer'].getvalue())
                for curl, errnum, errmsg in err_list:
                    #self._finish(curl, errnum, errmsg)
                    coev.switch(curl.info['thread_id'], 'booblik')
                if num_q == 0:
                    break

            while self._reqs and self._clients:
                (req, thid) = self._reqs.pop()
                client = self._clients.pop()

                _curl_setup_request(client, (req, thid))
                self._multi.add_handler(client)
                
            coev.stall()

def _curl_setup_request(curl, (req, thid)):
    buffer = cStringIO.StringIO() 
    
    curl.info = {
        'headers': {},
        'buffer': buffer,
        'request': req,
        'start_time': time.time(),
        'thread_id': thid,
    }

    curl.setopt(pycurl.URL, req.url)
    
    # headers here
    
    curl.setopt(pycurl.WRITEFUNCTION, buffer.write)
    
    return curl

http_client = HTTPClient()

class FutureResponse(frontik.future.FutureVal):
    def __init__(self, request):
        log.debug('scheduling %s', request.url)
    
        self.request = request
        self.data = None
    
    def _fetch_data(self):
        try:
            res = urllib2.urlopen(self.request.url).read()
            log.debug('got %s %s', 200, self.request.url)
        
        except urllib2.HTTPError, e:
            log.warn('failed %s %s', e.code, self.request.url)
            return et.Element('http-error', dict(url=self.request.url))
        
        else:
            try:
                return et.fromstring(res)
            except:
                return et.Element('xml-error', dict(url=self.request.url))
        
    def get(self):
        if not self.data:
            self.data = self._fetch_data()
            
        return self.data

def GET(url):
    ''' возвращает GET HTTPRequest с указанными параметрами '''
    return webob.Request.blank(url)

def POST(url):
    pass

def http(req):
    ''' 
    выполнить HTTP-вызов по заданному запросу
    @param req: webob.Request 
    '''
    
    ''' TODO здесь должен быть полноценный разбор webob.Request '''
    
    return FutureResponse(req)

def http_get(url):
    return http(GET(url))
