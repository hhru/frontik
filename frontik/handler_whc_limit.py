import weakref
import tornado.options

working_handlers_count = 0

class PageHandlerWHCLimit(object):
    def __init__(self, handler):
        self.handler = weakref.proxy(handler)
        
        # working handlers count
        global working_handlers_count
        self.acquired = False # init it with false in case of emergency failure

        if working_handlers_count <= tornado.options.options.handlers_count:
            self.handler.log.debug('started %s %s (workers_count = %s)',
                                   self.handler.request.method,
                                   self.handler.request.uri,
                                   working_handlers_count)
        else:
            self.handler.log.warn('dropping %s %s; too many handlers (%s)',
                                  self.handler.request.method,
                                  self.handler.request.uri,
                                  working_handlers_count)
            raise tornado.web.HTTPError(503)

        self.acquire()

    def acquire(self):
        if not self.acquired:
            global working_handlers_count
            working_handlers_count += 1
            self.acquired = True
            self.handler.log.debug('workers count+1 = %s', working_handlers_count)

    def release(self):
        if self.acquired:
            global working_handlers_count
            working_handlers_count -= 1
            
            self.acquired = False

            self.handler.log.debug('workers count-1 = %s', working_handlers_count)
