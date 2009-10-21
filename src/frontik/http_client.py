# -*- coding: utf-8 -*-

import webob
import urllib2

from frontik import etree as et
import frontik.future

class FutureResponse(frontik.future.FutureVal):
    def __init__(self, request):
        self.data = et.fromstring(urllib2.urlopen(request.url).read())
        
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
    
    return FutureResponse(req)

def http_get(url):
    return http(GET(url))
