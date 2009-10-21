# -*- coding: utf-8 -*-

import webob

import frontik.future
from frontik import etree as et

class Doc:
    def __init__(self, root_node_name='page'):
        self.root_node_name = root_node_name
        
        self.data = []
        
        self.put('<?xml version="1.0" ?>\n')
        self.put('<%s>' % (self.root_node_name,))
        
    def put(self, doc):
        self.data.append(doc)
    
    def _finalize_data(self):
        self.put('</%s>' % (self.root_node_name,))
        
        def chunk_to_string(chunk):
            # XXX изменится, при смене библиотеки!
            if isinstance(chunk, et._ElementInterface):
                return et.tostring(chunk)
            else:
                return chunk
        
        for chunk in self.data:
            if isinstance(chunk, frontik.future.FutureVal):
                yield chunk_to_string(chunk.get())
            else:
                yield chunk_to_string(chunk)
    
class DocResponse(object):
    def __init__(self, root_node_name='page'):
        self.response = webob.Response()
        self.response.content_type = 'application/xml'
        
        self.doc = Doc(root_node_name)
        
    def __call__(self, environ, start_response):
        for chunk in self.doc._finalize_data():
            self.response.write(chunk)
        
        return self.response(environ, start_response)
