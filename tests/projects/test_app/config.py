import os
import logging

logging.basicConfig()
logging.raiseExceptions = 0
XSL_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "xsl"))
XML_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "xml" ))
apply_xsl = True

XSL_cache_limit = 1
XML_cache_step = 1

def post(self, data, cb):
    self.log.debug('posprocessor called')
    cb(data)
    
postprocessor = post

