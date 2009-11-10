# -*- coding: utf-8 -*-

import webob

import frontik.future
from frontik import etree as et

class Doc:
    def __init__(self, root_node_name='page'):
        self.root_node_name = root_node_name
        
        self.data = []
        
        self.put('<%s>' % (self.root_node_name,))
        
    def put(self, doc):
        self.data.append(doc)
    
    def _finalize_data(self):
        self.put('</%s>\n' % (self.root_node_name,))
        
        def chunk_to_string(chunk):
            # XXX изменится, при смене библиотеки!
            if isinstance(chunk, et._ElementInterface):
                yield et.tostring(chunk)
            elif isinstance(chunk, Doc):
                for i in chunk._finalize_data():
                    yield i
            else:
                yield chunk
        
        for chunk in self.data:
            if isinstance(chunk, frontik.future.FutureVal):
                val = chunk.get()
            else:
                val = chunk
            
            for i in chunk_to_string(val):
                yield i
