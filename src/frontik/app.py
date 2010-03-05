import tornado.web
import tornado.ioloop
import logging
from tornado.options import options

log = logging.getLogger('frontik.server')        

import handler

class StatusHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('pages served: %s\n' % (handler.stats.page_count,))
        self.write('http reqs made: %s\n' % (handler.stats.http_reqs_count,))

class StopHandler(tornado.web.RequestHandler):
    def get(self):
        log.info('requested shutdown')
        tornado.ioloop.IOLoop.instance().stop()

class PagesDispatcher(object):

    def __init__(self, *args, **kwargs):
        self.frontik_www_config = kwargs["config"]

    def pages_dispatcher(self, application, request):
        log.info('requested url: %s', request.uri)
        
        page_module_name_parts = request.path.strip('/').split('/')[1:]

        if page_module_name_parts:
            page_module_name = '{0}.pages.{1}'.format('.'.join(options.app_package, page_module_name_parts))
        else:
            page_module_name = '{0}.pages'.format(options.app_package)
        
        try:
            page_module = __import__(page_module_name, fromlist=['Page'])
            log.debug('using %s from %s', page_module_name, page_module.__file__)
        except ImportError:
            log.exception('%s module not found', page_module_name)
            return tornado.web.ErrorHandler(application, request, 404)
        except:
            log.exception('error while importing %s module', page_module_name)
            return tornado.web.ErrorHandler(application, request, 500)
        
        try:
            request.config = self.frontik_www_config
            return page_module.Page(application, request)
        except:
            log.exception('%s.Page class not found', page_module_name)
            return tornado.web.ErrorHandler(application, request, 500) 

def get_app(config):
    return tornado.web.Application([
            (r'/status/', StatusHandler),
            (r'/stop/', StopHandler),
            (r'/page/.*', PagesDispatcher(config=config).pages_dispatcher),
            ])

