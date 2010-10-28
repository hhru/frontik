import logging
import tornado
import weakref
import xml.sax.saxutils
import os.path
import inspect
from StringIO import StringIO
from frontik import etree
from frontik import etree_builder as E
from datetime import datetime

def response_to_xml(response):
    headers = etree.Element("headers")
    time_info = etree.Element("time_info")
    
    try:
        body = etree.fromstring(response.body)
    except:
        body = unicode(response.body or "", "utf8")

    for name, value in response.headers.iteritems():
        headers.append(E.header(value, name=name))

    for name, value in response.time_info.iteritems():
        time_info.append(E.time(str(value), name=name))

    return (
        E.response(
            E.body(body),
            E.code(str(response.code)),
            E.effective_url(response.effective_url),
            E.error(str(response.error)),
            E.request_time(str(response.request_time)),
            headers,
            time_info,
        )
    )

class DebugPageHandler(logging.Handler):
    def __init__(self):
        """
        Initializes the instance - basically setting the formatter to None
        and the filter list to empty.
        """
        logging.Filterer.__init__(self)
        self.level = logging.DEBUG
        self.formatter = None
        #get the module data lock, as we're updating a shared structure.
        self.createLock()
        
        self.log_data = etree.Element("log") 

    def handle(self, record):
        fields = ['created', 'exc_info', 'exc_text', 'filename', 'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs', 'msg', 'name', 'pathname', 'process', 'processName', 'relativeCreated', 'threadName']
        entry = etree.Element("entry", **dict([(field, record.getMessage() if field == "msg" else str(getattr(record, field))) for field in fields if getattr(record, field) is not None]))
        entry.set("asctime", str(datetime.fromtimestamp(record.created)))

        if getattr(record, "response", None):
            entry.append(response_to_xml(record.response))
        self.log_data.append(entry)


class PageHandlerDebug(object):
    def __init__(self, handler):
        self.handler = weakref.proxy(handler)
    
        if self.handler.get_argument('debug', None) is not None:
            self.handler.log.debug('debug mode is on due to ?debug query arg')
            self.handler.require_debug_access()
            self.debug_mode = True
        else:
            self.debug_mode = False

        if tornado.options.options.debug or self.debug_mode:
            self.debug_mode_logging = True
            self.debug_log_handler = DebugPageHandler()
            self.handler.log.addHandler(self.debug_log_handler)

            self.handler.log.debug('using debug mode logging')
        else:
            self.debug_mode_logging = False

    def get_debug_page(self, status_code, **kwargs):
        self.handler.set_header('Content-Type', 'application/xml')
        if self.handler.get_argument('noxsl', None):
          try:
            xsl = open(os.path.dirname(inspect.currentframe().f_code.co_filename) + '/debug.xsl')
            xsl_code = xsl.read()
            xsl.close()
          except:
            xsl_code = '';
            
          log_document = etree.parse(StringIO('''<?xml version='1.0' encoding='UTF-8'?><!DOCTYPE debug [<!ELEMENT xsl:stylesheet ANY><!ATTLIST xsl:stylesheet id ID #REQUIRED>]>
              <?xml-stylesheet type="text/xsl" href="#style"?>
              <debug mode="''' + self.handler.get_argument('debug', 'text') + '''">
                 ''' + xsl_code + '''
              </debug>
              '''))
          log_document = log_document.getroot()
          log_document.append(self.debug_log_handler.log_data)
        else:
          log_document = self.debug_log_handler.log_data
          
        self.debug_log_handler.log_data.set("code", str(status_code))
        self.debug_log_handler.log_data.set("request-id", str(self.handler.request_id))
        return etree.tostring(etree.ElementTree(log_document), encoding='UTF-8', xml_declaration=True)
