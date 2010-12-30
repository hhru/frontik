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


class FrontikApp(object):
    def __init__(self, name, root, module, ph_globals):
        self.name = name
        self.root = root
        self.module = module
        self.ph_globals = ph_globals
        if getattr(module.config, 'rewriter', None) and callable(module.config.rewriter):
            self.rewriter = module.config.rewriter
        else:
            log.error('no rewriter specified for app "%s" or rewriter is not callable', name)
            self.rewriter = None


class HTTPRequestWrapper(HTTPRequest):
    def __init__(self, request, uri):
        HTTPRequest.__init__(self, request.method, uri, request.version, request.headers,
                 request.body, request.remote_ip, request.protocol, request.host,
                 request.files, request.connection)

class FrontikAppDispatcher(object):
    def __init__(self, app_roots):
        log.debug(app_roots)
        self.importer = frontik.magic_imp.FrontikAppImporter(app_roots)

        self.apps = {}
        for app_name, app_conf_tuple in app_roots.iteritems():
            (app_root, app_url_pattern, url_pre_rewriter) = app_conf_tuple
            try:
                # Track all possible filenames for each app's config
                # module to reload in case of change
                for filename in self.importer.get_probable_module_filenames(app_name, 'config'):
                    tornado.autoreload.watch_file(filename)

                module = self.init_app_package(app_name)
                ph_globals = frontik.handler.PageHandlerGlobals(module)
                self.apps[app_name] = FrontikApp(app_name, app_root, module, ph_globals), re.compile(app_url_pattern), url_pre_rewriter
            except:
                # we do not want to break frontik on app
                # initialization error, so we report error and skip
                # the app.
                self.apps.append[app_name] = None, re.compile(app_url_pattern), None
                log.exception('failed to initialize %s, skipping from configuration', app_name)

    def init_app_package(self, app_name):
        module = imp.new_module(frontik.magic_imp.gen_module_name(app_name))
        sys.modules[module.__name__] = module

        pages_module = imp.new_module(frontik.magic_imp.gen_module_name(app_name, 'pages'))
        sys.modules[pages_module.__name__] = pages_module

        try:
            module.config = self.importer.imp_app_module(app_name, 'config')
        except:
            log.error('failed to load config for app "%s"', app_name)
            raise

        return module

    def dispatch(self, application, request):
        log.info('requested url: %s', request.uri)

        page_module_name = None

        for name, app_tuple in self.apps.iteritems():
            app, pattern, rewriter = app_tuple
            match = pattern.match(request.uri)
            if match:
                app_name = name
                if not app:
                    log.exception('%s application not loaded, because of fail during initialization', app_name)
                    return tornado.web.ErrorHandler(application, request, 404)
                uri = request.uri

                if callable(rewriter):
                    uri = rewriter(match, request.uri)
                    log.debug('prerewrited url: %s', uri)
                    request = HTTPRequestWrapper(request, uri)
                else:
                    log.debug('%s specified application prerewriter is not callable, skiping prerewrite', app_name)

                if callable(app.rewriter):
                    uri = app.rewriter(request.uri)
                    log.debug('rewrited url: %s', uri)
                    request = HTTPRequestWrapper(request, uri)
                else:
                    log.debug('%s specified application rewriter is not callable, skiping rewrite', app_name)

                page_module_name = 'pages.'+ '.'.join( filter( lambda x: x != '' , uri.rstrip('/').split('?')[0].split('/')))
                log.debug('page module: %s', page_module_name)
                break #app found

        if not page_module_name:
            log.exception('application for request url "%s" not found', request.uri)
            return tornado.web.ErrorHandler(application, request, 404)

        try:
            page_module = self.importer.imp_app_module(app_name, page_module_name)
            log.debug('using %s from %s', (app_name, page_module_name), page_module.__file__)
        except ImportError:
            log.exception('%s module not found', (app_name, page_module_name))
            return tornado.web.ErrorHandler(application, request, 404)
        except:
            log.exception('error while importing %s module', (app_name, page_module_name))
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

        return tornado.web.ErrorHandler(application, request, 404)

def get_app(app_roots):
    dispatcher = FrontikAppDispatcher(app_roots)
    
    return tornado.web.Application([
        (r'/version/', VersionHandler),
        (r'/status/', StatusHandler),
        (r'/stop/', StopHandler),
        (r'/types_count/', CountTypesHandler),
        (r'/pdb/', PdbHandler),
        (r'/ph_count/', CountPageHandlerInstancesHandler),
        (r'/.*', dispatcher.dispatch),
        ])

