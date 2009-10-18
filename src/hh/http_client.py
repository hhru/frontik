# -*- coding: utf-8 -*-

import webob
import urllib2
import xml.etree.ElementTree as et

class FutureResponse:
    def __init__(self, request):
        self.data = et.fromstring(urllib2.urlopen(request.url).read())
        
    def get(self):
        return et.tostring(self.data)

def GET(url):
    ''' возвращает GET HTTPRequest с указанными параметрами '''
    return webob.Request.blank(url)

def POST(url):
    pass

def http(req):
    return FutureResponse(req)

def http_get(url):
    return http(GET(url))
