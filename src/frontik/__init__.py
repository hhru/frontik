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

import tornado.web

class PageHandler(tornado.web.RequestHandler):
    def __init__(self, *args, **kw):
        tornado.web.RequestHandler.__init__(self, *args, **kw)
        
        self.doc = Doc()
    
    def finish(self, data=None):
        data = list(self.doc._finalize_data())
        
        self.set_header('Content-Type', 'application/xml')
        self.write('<?xml version="1.0" ?>\n')
        
        for chunk in data:
            self.write(chunk)
        
        tornado.web.RequestHandler.finish(self, '')
    
