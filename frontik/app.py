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
import urlparse

log = logging.getLogger('frontik.server')

import frontik.handler as handler
import functools

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


def augment_request(request, match, parse):
    new_uri = request.uri[:match.start()] + request.uri[match.end():]
    (scheme, netloc, request.path, request.query, fragment), request.uri = \
    urlparse.urlsplit(new_uri), new_uri

    arguments = match.groupdict()
    for name, value in arguments.iteritems():
        if value:
            request.arguments.setdefault(name, []).extend(parse(value))

def dispatcher(cls):
    'makes on demand initializing class'
    old_init = cls.__init__
    def __init__(self, *args, **kwargs):
        self._init_partial = functools.partial(old_init, self, *args, **kwargs)
        self._inited = False

    def _initialize(self):
        if not self._inited:
            self._init_partial()
            self._inited = True
        return self._inited

    on_demand = type(cls.__name__, (cls,), dict(__init__=__init__, _initialize=_initialize))
    return on_demand


@dispatcher
class Map2ModuleName(object):
    def __init__(self, module):
        self.module = module
        self.name = module.__name__
        self.log = logging.getLogger('frontik.map2pages.{0}'.format(self.name))
        self.log.info('initializing...')

    def __call__(self, application, request, **kwargs):
        self.log.info('requested url: %s', request.uri)

        page_module_name = 'pages.' + '.'.join(request.path.strip('/').split('/'))
        self.log.debug('page module: %s', page_module_name)

        try:
            page_module = self.module.frontik_import(page_module_name)
            self.log.debug('using %s from %s', (self.name, page_module_name), page_module.__file__)
        except ImportError:
            self.log.exception('%s module not found', (self.name, page_module_name))
            return tornado.web.ErrorHandler(application, request, 404)
        except AttributeError:
            self.log.exception('%s is not frontik application module, but needs to be and have "frontik_import" method', self.name)
            return tornado.web.ErrorHandler(application, request, 500)
        except:
            self.log.exception('error while importing %s module', (self.name, page_module_name))
            return tornado.web.ErrorHandler(application, request, 500)

        if not hasattr(page_module, 'Page'):
            log.exception('%s. Page class not found', page_module_name)
            return tornado.web.ErrorHandler(application, request, 404)

        return page_module.Page(application, request, **kwargs)


@dispatcher
class App(object):
    def __init__(self, name, root):
        self.log = logging.getLogger('frontik.application.{0}'.format(name))
        self.initialized_wo_error = True

        self.log.info('initializing...')
        try:
            self.importer = frontik.magic_imp.FrontikAppImporter(name, root)

            self.init_app_package(name)

            #Track all possible filenames for each app's config
            #module to reload in case of change
            for filename in self.importer.get_probable_module_filenames('config'):
                tornado.autoreload.watch_file(filename)

            self.ph_globals = frontik.handler.PageHandlerGlobals(self.module)
        except:
            #we do not want to break frontik on app
            #initialization error, so we report error and skip
            #the app.
            self.log.exception('failed to initialize, skipping from configuration')
            self.initialized_wo_error = False

    def init_app_package(self, name):
        self.module = imp.new_module(frontik.magic_imp.gen_module_name(name))
        sys.modules[self.module.__name__] = self.module

        self.pages_module = self.importer.imp_app_module('pages')
        sys.modules[self.pages_module.__name__] = self.pages_module

        try:
            self.module.config = self.importer.imp_app_module('config')
        except Exception, e:
            self.log.error('failed to load config: %s', e)
            raise

        if not hasattr(self.module.config, 'urls'):
            self.module.config.urls = [("", Map2ModuleName(self.pages_module)),]
        self.module.dispatcher = RegexpDispatcher(self.module.config.urls, self.module.__name__)
        self.module.dispatcher._initialize()

    def __call__(self, application, request, **kwargs):
        self.log.info('requested url: %s', request.uri)
        if not self.initialized_wo_error:
            self.log.exception('%s application not loaded, because of fail during initialization', self.name)
            return tornado.web.ErrorHandler(application, request, 404)
        return self.module.dispatcher(application, request, ph_globals = self.ph_globals, **kwargs)

@dispatcher
class RegexpDispatcher(object):
    def __init__(self, app_list, name='RegexpDispatcher'):
        self.name = name
        self.log = logging.getLogger('frontik.dispatcher.{0}'.format(name))
        self.log.info('initializing...')

        def parse_conf(pattern, app, parse=lambda x: [x,]):
            try:
                app._initialize()
            except AttributeError:
                #its mean that app is not dispatcher -> nothing to _initialize
                pass
            return re.compile(pattern), app, parse

        self.apps = map(lambda app_conf: parse_conf(*app_conf), app_list)

    def __call__(self, application, request, **kwargs):
        self.log.info('requested url: %s', request.uri)
        for pattern, app, parse in self.apps:

            match = pattern.match(request.uri)
            #app found
            if match:
                augment_request(request, match, parse)
                try:
                    return app(application, request, **kwargs)
                except tornado.web.HTTPError, e:
                    log.exception('%s. Tornado error, %s', app, e)
                    return tornado.web.ErrorHandler(application, request, e.status_code)
                except Exception, e:
                    log.exception('%s. Internal server error, %s', app, e)
                return tornado.web.ErrorHandler(application, request, 500)

        self.log.exception('match for request url "%s" not found', request.uri)
        return tornado.web.ErrorHandler(application, request, 404)

def get_app(app_urls, app_dict={}):
    app_roots = []
    app_roots.extend([('/'+prefix.lstrip('/'), App(prefix.strip('/'), path)) for prefix, path in app_dict.iteritems()])
    app_roots.extend(app_urls)
    dispatcher = RegexpDispatcher(app_roots, 'root')
    dispatcher._initialize()

    return tornado.web.Application([
        (r'/version/', VersionHandler),
        (r'/status/', StatusHandler),
        (r'/stop/', StopHandler),
        (r'/types_count/', CountTypesHandler),
        (r'/pdb/', PdbHandler),
        (r'/ph_count/', CountPageHandlerInstancesHandler),
        (r'/.*', dispatcher),
        ])
