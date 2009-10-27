# -*- coding: utf-8 -*-

import webob
import urllib
import urllib2
import logging

from frontik import etree as et
import future

log = logging.getLogger('frontik.http_client')

def make_url(base, **query_args):
    ''' 
    построить URL из базового урла и набора CGI-параметров
    параметры с пустым значением пропускаются, удобно для последовательности:
    make_url(base, hhtoken=request.cookies.get('hhtoken'))
    '''
    
    kv_pairs = []
    for (key, val) in query_args.iteritems():
        if val:
            if isinstance(val, list):
                for v in val:
                    kv_pairs.append((key, v))
            else:
                kv_pairs.append((key, val))
    
    qs = urllib.urlencode(kv_pairs)
    
    if qs:
        return base + '?' + qs
    else:
        return base 

class FutureResponse(future.FutureVal):
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
