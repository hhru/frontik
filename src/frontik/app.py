import tornado.web
import tornado.ioloop
import tornado.options
import logging
import importer
import os


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

    def __init__(self, options):
        self.options = options

    def pages_dispatcher(self, application, request):
        log.info('requested url: %s', request.uri)
        page_module_name_parts = request.path.strip('/').split('/')[1:]
        application_name = page_module_name_parts[0]
        page_module_name = page_module_name_parts[-1:][0]
        
        try:
            page_module_path = self.options.document_roots[application_name]
            page_module = importer.import_path(page_module_name, os.path.join(page_module_path, "pages/"), "frontik_app__%s" % application_name)
            page_config = importer.import_path("config", page_module_path, "frontik_app__%s__config" % application_name)

            log.debug('using %s from %s', page_module_name, page_module.__file__)
        except ImportError:
            log.exception('%s module not found', page_module_name)
            return tornado.web.ErrorHandler(application, request, 404)
        except:
            log.exception('error while importing %s module', page_module_name)
            return tornado.web.ErrorHandler(application, request, 500)
        
        try:
            request.application_class = page_module.Page
            request.application_config = page_config

            return handler.PageHandler(application, request)
            #return page_module.Page(application, request)
        except Exception, error:
            log.exception('%s.Page class not found', page_module_name)
            return tornado.web.ErrorHandler(application, request, 404) 

def get_app(options):
    return tornado.web.Application([
            (r'/status/', StatusHandler),
            (r'/stop/', StopHandler),
            (r'/page/.*', PagesDispatcher(options).pages_dispatcher),
            ])

