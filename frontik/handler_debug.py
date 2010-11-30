import logging
import tornado
import weakref
import xml.sax.saxutils

_debug_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
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
        self.log_data = []

    def handle(self, record):
        self.log_data.append(_debug_formatter.format(record))


class PageHandlerDebug(object):
    def __init__(self, handler):
        self.handler = weakref.proxy(handler)
    
        if self.handler.get_argument('debug', None) is not None:
            self.handler.require_debug_access()
            self.debug_mode = True
            self.handler.log.debug('debug mode is on due to ?debug query arg')
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
        return '<html><title>{code}</title>' \
            '<body>' \
            '<h1>{code}</h1>' \
            '<pre>{log}</pre></body>' \
            '</html>'.format(code=status_code,
                             log='<br/>'.join(xml.sax.saxutils.escape(i).replace('\n', '<br/>').replace(' ', '&nbsp;')
                                              for i in self.debug_log_handler.log_data))
