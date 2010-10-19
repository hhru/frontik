import sys
import os.path
import imp

import tornado.web
import tornado.ioloop
import frontik.log as logging
from tornado.options import options

import frontik.magic_imp
import frontik.version
import frontik.doc
from frontik import etree

log = logging.getLogger('frontik.server')        

import handler

class VersionHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'text/xml')

        project_el = etree.Element("project", name="frontik")
        version_el = etree.Element("version")
        project_el.append(version_el)

        version_el.text = frontik.version.version
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

class FrontikAppDispatcher(object):
    def __init__(self, app_roots):
        self.importer = frontik.magic_imp.FrontikAppImporter(app_roots)

        self.apps = {}
        for (app_name, app_root) in app_roots.iteritems():
            module = self.init_app_package(app_name)
            ph_globals = frontik.handler.PageHandlerGlobals(module)
            self.apps[app_name] = FrontikApp(app_name, app_root, module, ph_globals)

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

        page_module_name_parts = request.path.strip('/').split('/')

        app_name = page_module_name_parts[0]
        page_module_name = '.'.join(['pages'] + page_module_name_parts[1:])

        app = self.apps[app_name]

        try:
            page_module = self.importer.imp_app_module(app_name, page_module_name)
            log.debug('using %s from %s', (app_name, page_module_name), page_module.__file__)
        except ImportError:
            log.exception('%s module not found', (app_name, page_module_name))
            return tornado.web.ErrorHandler(application, request, 404)
        except:
            log.exception('error while importing %s module', (app_name, page_module_name))
            return tornado.web.ErrorHandler(application, request, 500)

        try:
            return page_module.Page(app.ph_globals, application, request)
        except:
            log.exception('%s.Page class not found', page_module_name)
            return tornado.web.ErrorHandler(application, request, 500)

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

