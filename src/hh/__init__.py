from webob import Request, Response

class Page:
    def __init__(self, xml_node_name='page'):
        self.response = Response()
        self.response.content_type = 'application/xml'
        self.response.write('<?xml version="1.0" ?>')
        self.response.write('<page>')
        
    def put(self, doc):
        self.response.write(doc)
        
    def __call__(self, environ, start_response):
        self.response.write('</page>')
        
        return self.response(environ, start_response)

