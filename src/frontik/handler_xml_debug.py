import logging
import tornado
import weakref
import xml.sax.saxutils
from frontik import etree
from frontik import etree_builder as E
from datetime import datetime

def response_to_xml(response):
    headers = etree.Element("headers")
    time_info = etree.Element("time_info")

    for name, value in response.headers.iteritems():
        headers.append(E.header(value, name=name))

    for name, value in response.time_info.iteritems():
        time_info.append(E.time(str(value), name=name))

    return (
        E.response(
            E.body(unicode(response.body or "", "utf8")),
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
        self.debug_log_handler.log_data.set("code", str(status_code))
        return etree.tostring(self.debug_log_handler.log_data)
