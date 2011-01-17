import imp
import logging
import os.path
import sys
import re

import lxml.etree as etree
import tornado.autoreload
import tornado.web
import tornado.ioloop
from tornado.options import options

import frontik.magic_imp
import frontik.doc
from frontik import __version__
from frontik import etree
from tornado.httpserver import HTTPRequest

log = logging.getLogger('frontik.server')        

import frontik.handler as handler

class VersionHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'text/xml')

        project_el = etree.Element("project", name="frontik")
        version_el = etree.Element("version")
        project_el.append(version_el)

        version_el.text = __version__
        self.write(frontik.doc.etree_to_xml(project_el))


class StatusHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('pages served: %s\n' % (handler.stats.page_count,))
        self.write('http reqs made: %s\n' % (handler.stats.http_reqs_count,))


class StopHandler(tornado.web.RequestHandler):
    def get(self):
        log.info('requested shutdown')
        tornado.ioloop.IOLoop.instance().stop()


class PdbHandler(tornado.web.RequestHandler):
    def get(self):
        import pdb
        pdb.set_trace()


class CountPageHandlerInstancesHandler(tornado.web.RequestHandler):
    def get(self):
        import gc
        import frontik.handler
        hh = tuple([i for i in gc.get_objects()
                    if isinstance(i, frontik.handler.PageHandler)])

        #if len(hh) > 0:
        #    import pdb; pdb.set_trace()

        self.finish('{0}\n{1}'.format(len(hh), [i for i in gc.get_referrers(*hh)
                                                if i is not hh]))

class CountTypesHandler(tornado.web.RequestHandler):
    def get(self):
        import gc
        from collections import defaultdict

        counts = defaultdict(int)

        for o in gc.get_objects():
            counts[type(o)] += 1

        for k, v in sorted(counts.items(), key=lambda x:x[0]):
            self.write('%s\t%s\n' % (v, k))

        self.finish()


class RequestWrapper(HTTPRequest):
    def __init__(self, request, match):
        super(RequestWrapper, self).__init__(request.method, request.uri, request.version, request.headers,
                 request.body, request.remote_ip, request.protocol, request.host,
                 request.files, request.connection)
        arguments = match.groupdict()
        for name, value in arguments.iteritems():
            if value: self.arguments.setdefault(name, []).append(value)

#TODO: MAYBE split this into:
#TODO:      1. load "path/to/python/module" and call "dispatch" from whitin
#TODO:      2. load "path/to/python/pages/module" and map url to file system
class App(object):
    def __init__(self, name, root):
        self.name = name
        self.root = root
        self.module = module
        self.ph_globals = ph_globals
        if getattr(module.config, 'rewriter', None) and callable(module.config.rewriter):
            self.rewriter = module.config.rewriter
        else:
            log.error('no rewriter specified for app "%s" or rewriter is not callable', name)
            self.rewriter = None

            #Track all possible filenames for each app's config
            #module to reload in case of change
            for filename in self.importer.get_probable_module_filenames(self.name, 'config'):
                tornado.autoreload.watch_file(filename)

            self.ph_globals = frontik.handler.PageHandlerGlobals(self.module)
        except:
            #we do not want to break frontik on app
            #initialization error, so we report error and skip
            #the app.
            self.log.exception('failed to initialize, skipping from configuration')
            self.initialized_wo_error = False

    #TODO: move this to (magic)_imp or somewhere else
    def init_app_package(self):
        self.module = imp.new_module(frontik.magic_imp.gen_module_name(self.name))
        sys.modules[self.module.__name__] = self.module

        self.pages_module = imp.new_module(frontik.magic_imp.gen_module_name(self.name, 'pages'))
        sys.modules[self.pages_module.__name__] = self.pages_module

        try:
            self.module.config = self.importer.imp_app_module(self.name, 'config')
        except:
            self.log.error('failed to load config')
            raise

    def __call__(self, application, request):
        return self.dispatch(application, request)

    def dispatch(self, application, request):
        log.info('requested url: %s', request.uri)

        page_module_name = None
        app_name = None

        for name, app_tuple in self.apps.iteritems():
            app, pattern, rewriter = app_tuple
            match = pattern.match(request.uri)
            if match:
                if not app:
                    log.exception('%s application not loaded, because of fail during initialization', app_name)
                    return tornado.web.ErrorHandler(application, request, 404)

                uri = request.uri

                #config level rewrite
                if callable(rewriter):
                    uri = rewriter(match, request.uri)
                    log.debug('prerewrited url: %s', uri)
                    request = RequestWrapper(request, uri)
                else:
                    log.debug('%s specified application prerewriter is not callable, skiping prerewrite', app_name)

                #app level rewrite
                if callable(app.rewriter):
                    uri = app.rewriter(request.uri)
                    log.debug('rewrited url: %s', uri)
                    request = RequestWrapper(request, uri)
                else:
                    log.debug('%s specified application rewriter is not callable, skiping rewrite', app_name)

                app_name = name
                page_module_name = 'pages.'+ '.'.join(request.path.strip('/').split('/'))
                log.debug('page module: %s', page_module_name)
                break #app found

        if not page_module_name:
            log.exception('application for request url "%s" not found', request.uri)
            return tornado.web.ErrorHandler(application, request, 404)

        page_module_name = 'pages.'+ '.'.join(request.path.strip('/').split('/'))
        self.log.debug('page module: %s', page_module_name)

        try:
            page_module = self.importer.imp_app_module(self.name, page_module_name)
            self.log.debug('using %s from %s', (self.name, page_module_name), page_module.__file__)
        except ImportError:
            self.log.exception('%s module not found', (self.name, page_module_name))
            return tornado.web.ErrorHandler(application, request, 404)
        except:
            self.log.exception('error while importing %s module', (self.name, page_module_name))
            return tornado.web.ErrorHandler(application, request, 500)

        if not hasattr(page_module, 'Page'):
            log.exception('%s. Page class not found', page_module_name)
            return tornado.web.ErrorHandler(application, request, 404)
        try:
            return page_module.Page(app.ph_globals, application, request)
        except tornado.web.HTTPError, e:
            log.exception('%s. Tornado error, %s', page_module_name, e)
            return tornado.web.ErrorHandler(application, request, e.status_code)
        except Exception, e:
            log.exception('%s. Internal server error, %s', page_module_name, e)
            return tornado.web.ErrorHandler(application, request, 500)

class RegexpDispatcher(object):
    def __init__(self, app_roots, name = 'RegexpDispatcher'):
        self.name = name
        self.log = logging.getLogger('frontik.dispatcher.{0}'.format(name))
        self.apps = [ (app, re.compile(app_pattern)) for app_pattern, app in app_roots]

    def __call__(self, application, request):
        return self.dispatch(application, request)

    def dispatch(self, application, request):
        log.info('requested url: %s', request.uri)
        log.info(self.apps)
        for app_tuple in self.apps:
            app, pattern = app_tuple
            match = pattern.match(request.uri)

            #app found
            if match:
                request = RequestWrapper(request, match)
                return app(application, request)

        log.exception('application for request url "%s" not found', request.uri)
        return tornado.web.ErrorHandler(application, request, 404)

def get_app(app_roots):
    dispatcher = RegexpDispatcher(app_roots, 'root')
    
    return tornado.web.Application([
        (r'/version/', VersionHandler),
        (r'/status/', StatusHandler),
        (r'/stop/', StopHandler),
        (r'/types_count/', CountTypesHandler),
        (r'/pdb/', PdbHandler),
        (r'/ph_count/', CountPageHandlerInstancesHandler),
        (r'/.*', dispatcher.dispatch),
        ])

