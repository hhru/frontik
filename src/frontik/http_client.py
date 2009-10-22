# -*- coding: utf-8 -*-

import webob
import urllib2
import logging

from frontik import etree as et
import frontik.future

log = logging.getLogger('frontik.http_client')

class FutureResponse(frontik.future.FutureVal):
    def __init__(self, request):
        try:
            res = urllib2.urlopen(request.url).read()
            
        except urllib2.HTTPError, e:
            self.data = et.Element('http-error', dict(url=request.url))
            
        else:
            try:
                self.data = et.fromstring(res)
            except:
                self.data = et.Element('xml-error', dict(url=request.url))

        
    def get(self):
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
    
    log.debug('http: %s', req.url)
    
    return FutureResponse(req)

def http_get(url):
    return http(GET(url))
