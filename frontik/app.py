import imp
import logging
import sys
import re
import time
import functools
import urlparse

import lxml.etree as etree
import tornado.autoreload
import tornado.web
import tornado.ioloop
from tornado.options import options

import frontik.handler as handler
import frontik.magic_imp
import frontik.doc


log = logging.getLogger('frontik.server')

def __get_apps_versions():
    app_versions = etree.Element('applications')

    for path, app in options.urls:
        app_info = etree.Element('application', name=repr(app), path=path)
        try:
            application = app.ph_globals.config.version
            app_info.extend(list(application))
        except:
            etree.SubElement(app_info, 'version').text = 'app doesn''t support version'

        etree.SubElement(app_info, 'initialized_wo_error').text = str(app.initialized_wo_error)
        app_versions.append(app_info)

    return app_versions

def get_frontik_and_apps_versions():
    from version import version
    versions = etree.Element('versions')
    etree.SubElement(versions, 'frontik').text = version
    versions.append(__get_apps_versions())
    return versions


class VersionHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'text/xml')
        self.write(frontik.doc.etree_to_xml(get_frontik_and_apps_versions()))


class StatusHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'text/plain; charset=UTF-8')
        self.write('pages served: %s\n' % (handler.stats.page_count,))
        self.write('http reqs made: %s\n' % (handler.stats.http_reqs_count,))
        self.write('http reqs got: %s bytes\n' % (handler.stats.http_reqs_size_sum,))
        cur_uptime = time.time() - handler.stats.start_time
        if cur_uptime < 60:
            res = 'uptime for : %d seconds\n' % cur_uptime
        elif cur_uptime < 3600:
            res = 'uptime for : %d minutes\n' % ((cur_uptime/60),)
        else:
            res = 'uptime for : %d hours and %d minutes \n' % (cur_uptime/3600, (cur_uptime % 3600)/60)

        self.write(res)


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


def get_to_dispatch(request, field = 'path'):
    if hasattr(request, 're_'+field):
        return getattr(request, 're_'+field)
    return getattr(request, field)

def set_to_dispatch(request, value, field = 'path'):
    setattr(request, 're_'+field, value)

def augment_request(request, match, parse):
    uri = get_to_dispatch(request, 'uri')

    new_uri = (uri[:match.start()] + uri[match.end():])
    split = urlparse.urlsplit(new_uri[:1] +  new_uri[1:].strip('/'))

    set_to_dispatch(request, new_uri, 'uri')
    set_to_dispatch(request, split.path, 'path')
    set_to_dispatch(request, split.query, 'query')

    arguments = match.groupdict()
    for name, value in arguments.iteritems():
        if value:
            request.arguments.setdefault(name, []).extend(parse(value))

def dispatcher(cls):
    """makes on demand initializing class"""
    old_init = cls.__init__
    def __init__(self, *args, **kwargs):
        self._init_partial = functools.partial(old_init, self, *args, **kwargs)
        self._inited = False

    def __repr__(self):
        return '{0}.{1}: {2}'.format(cls.__module__, cls.__name__, self.name)

    def _initialize(self):
        if not self._inited:
            self._init_partial()
            self._inited = True
        return self._inited

    on_demand = type(cls.__name__, (cls,), dict(__init__=__init__, _initialize=_initialize, __repr__=__repr__))
    return on_demand


@dispatcher
class Map2ModuleName(object):
    def __init__(self, module):
        self.module = module
        self.name = module.__name__
        self.log = logging.getLogger('frontik.map2pages.{0}'.format(self.name))
        self.log.info('initializing...')

    def __call__(self, application, request, **kwargs):
        self.log.info('requested url: %s (%s)', get_to_dispatch(request, 'uri'), request.uri)

        page_module_name = 'pages.' + '.'.join(get_to_dispatch(request,'path').strip('/').split('/'))
        self.log.debug('page module: %s', page_module_name)

        try:
            page_module = self.module.frontik_import(page_module_name)
            self.log.debug('using %s from %s', (self.name, page_module_name), page_module.__file__)
        except ImportError:
            self.log.exception('%s module not found', (self.name, page_module_name))
            return tornado.web.ErrorHandler(application, request, status_code=404)
        except AttributeError:
            self.log.exception('%s is not frontik application module, but needs to be and have "frontik_import" method', self.name)
            return tornado.web.ErrorHandler(application, request, status_code=500)
        except:
            self.log.exception('error while importing %s module', (self.name, page_module_name))
            return tornado.web.ErrorHandler(application, request, status_code=500)

        if not hasattr(page_module, 'Page'):
            log.exception('%s. Page class not found', page_module_name)
            return tornado.web.ErrorHandler(application, request, status_code=404)

        return page_module.Page(application, request, **kwargs)


@dispatcher
class App(object):
    def __init__(self, name, root):
        self.log = logging.getLogger('frontik.application.{0}'.format(name))
        self.name = name
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
        self.log.info('requested url: %s (%s)', get_to_dispatch(request, 'uri'), request.uri)
        if not self.initialized_wo_error:
            self.log.exception('application not loaded, because of fail during initialization')
            return tornado.web.ErrorHandler(application, request, status_code=404)
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
        self.log.info('requested url: %s (%s)', get_to_dispatch(request, 'uri'), request.uri)
        for pattern, app, parse in self.apps:

            match = pattern.match(get_to_dispatch(request, 'uri'))
            #app found
            if match:
                self.log.debug('using %s' % app)
                augment_request(request, match, parse)
                try:
                    return app(application, request, **kwargs)
                except tornado.web.HTTPError, e:
                    log.exception('%s. Tornado error, %s', app, e)
                    return tornado.web.ErrorHandler(application, request, e.status_code)
                except Exception, e:
                    log.exception('%s. Internal server error, %s', app, e)
                return tornado.web.ErrorHandler(application, request, status_code=500)

        self.log.exception('match for request url "%s" not found', request.uri)
        return tornado.web.ErrorHandler(application, request, status_code=404)

def get_app(app_urls, app_dict=None):
    app_roots = []
    if app_dict is not None:
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
