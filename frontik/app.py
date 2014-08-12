# coding=utf-8

import functools
import imp
import logging
import re
import sys
import time
import urlparse

from lxml import etree
import tornado.autoreload
import tornado.web
import tornado.ioloop
from tornado.options import options

from frontik.globals import global_stats
from frontik.handler import ApplicationGlobals, PageHandler
import frontik.magic_imp
import frontik.xml_util

log = logging.getLogger('frontik.server')


def _get_apps_versions():
    app_versions = etree.Element('applications')

    for path, app in options.urls:
        app_info = etree.Element('application', name=repr(app), path=path)
        try:
            application = app.app_globals.config.version
            app_info.extend(list(application))
        except:
            etree.SubElement(app_info, 'version').text = 'app doesn''t support version'

        etree.SubElement(app_info, 'initialized_wo_error').text = str(app.initialized_wo_error)
        app_versions.append(app_info)

    return app_versions


def get_frontik_and_apps_versions():
    from frontik.version import version
    versions = etree.Element('versions')
    etree.SubElement(versions, 'frontik').text = version
    versions.append(_get_apps_versions())
    return versions


class VersionHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'text/xml')
        self.write(etree.tostring(get_frontik_and_apps_versions(), encoding='utf-8', xml_declaration=True))


class StatusHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')

        result = {
            'pages served': global_stats.page_count,
            'http requests made': global_stats.http_reqs_count,
            'bytes from http requests': global_stats.http_reqs_size_sum,
        }

        cur_uptime = time.time() - global_stats.start_time
        if cur_uptime < 60:
            uptime_value = '{:.2f} seconds'.format(cur_uptime)
        elif cur_uptime < 3600:
            uptime_value = '{:.2f} minutes'.format(cur_uptime / 60)
        else:
            uptime_value = '{:.2f} hours and {:.2f} minutes'.format(cur_uptime / 3600, (cur_uptime % 3600) / 60)

        result['uptime'] = uptime_value

        self.write(result)


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
        hh = tuple([i for i in gc.get_objects() if isinstance(i, PageHandler)])

        self.finish('{0}\n{1}'.format(len(hh), [i for i in gc.get_referrers(*hh) if i is not hh]))


class CountTypesHandler(tornado.web.RequestHandler):
    def get(self):
        import gc
        from collections import defaultdict

        counts = defaultdict(int)

        for o in gc.get_objects():
            counts[type(o)] += 1

        for k, v in sorted(counts.items(), key=lambda x: x[0]):
            self.write('%s\t%s\n' % (v, k))

        self.finish()


def get_to_dispatch(request, field='path'):
    return getattr(request, 're_' + field, getattr(request, field))


def set_to_dispatch(request, value, field='path'):
    setattr(request, 're_' + field, value)


def augment_request(request, match, parse):
    uri = get_to_dispatch(request, 'uri')

    new_uri = (uri[:match.start()] + uri[match.end():])
    split = urlparse.urlsplit(new_uri[:1] + new_uri[1:].strip('/'))

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
class FileMappingDispatcher(object):
    def __init__(self, module, handler_404=None):
        self.module = module
        self.name = module.__name__
        self.handler_404 = handler_404
        self.log = logging.getLogger('frontik.filemapping.{0}'.format(self.name))
        self.log.info('initializing...')

    def __call__(self, application, request, **kwargs):
        self.log.info('requested url: %s (%s)', get_to_dispatch(request, 'uri'), request.uri)

        page_module_name = 'pages.' + '.'.join(filter(None, get_to_dispatch(request, 'path').strip('/').split('/')))
        self.log.debug('page module: %s', page_module_name)

        try:
            page_module = self.module.frontik_import(page_module_name)
            self.log.debug('using %s from %s', (self.name, page_module_name), page_module.__file__)
        except ImportError:
            self.log.exception('%s module not found', (self.name, page_module_name))
            if self.handler_404 is not None:
                return self.handler_404
            return tornado.web.ErrorHandler(application, request, status_code=404)
        except AttributeError:
            self.log.exception('%s is not frontik application module (no "frontik_import" method)', self.name)
            return tornado.web.ErrorHandler(application, request, status_code=500)
        except:
            self.log.exception('error while importing %s module', (self.name, page_module_name))
            return tornado.web.ErrorHandler(application, request, status_code=500)

        if not hasattr(page_module, 'Page'):
            log.error('%s. Page class not found', page_module_name)
            return tornado.web.ErrorHandler(application, request, status_code=404)

        return page_module.Page(application, request, **kwargs)

# Deprecated synonym
Map2ModuleName = FileMappingDispatcher


@dispatcher
class App(object):
    class DefaultConfig(object):
        pass

    def __init__(self, name, root, config=None):
        self.log = logging.getLogger('frontik.application.{0}'.format(name))
        self.name = name
        self.initialized_wo_error = True

        self.log.info('initializing...')
        try:
            self.importer = frontik.magic_imp.FrontikAppImporter(name, root)
            self.init_app_package(name, config)
            self.app_globals = ApplicationGlobals(self.module)
        except:
            # we do not want to break frontik on app initialization error,
            # so we report error and skip the app.
            self.log.exception('failed to initialize, skipping from configuration')
            self.initialized_wo_error = False

    def init_app_package(self, name, config=None):
        self.module = imp.new_module(frontik.magic_imp.gen_module_name(name))
        sys.modules[self.module.__name__] = self.module

        self.pages_module = self.importer.imp_app_module('pages')
        sys.modules[self.pages_module.__name__] = self.pages_module

        if config is not None:
            self.module.config = config
        else:
            try:
                self.module.config = self.importer.imp_app_module('config')
                # track all possible filenames for each app's config module to reload in case of change
                for filename in self.importer.get_probable_module_filenames('config'):
                    tornado.autoreload.watch_file(filename)
            except ImportError:
                self.module.config = App.DefaultConfig()
                self.log.warn('no config.py file, using empty default')

        if not hasattr(self.module.config, 'urls'):
            self.module.config.urls = [('', Map2ModuleName(self.pages_module))]

        self.module.dispatcher = RegexpDispatcher(self.module.config.urls, self.module.__name__)
        self.module.dispatcher._initialize()

    def __call__(self, application, request, **kwargs):
        self.log.info('requested url: %s (%s)', get_to_dispatch(request, 'uri'), request.uri)
        if not self.initialized_wo_error:
            self.log.exception('application not loaded, because of fail during initialization')
            return tornado.web.ErrorHandler(application, request, status_code=404)
        return self.module.dispatcher(application, request, app_globals=self.app_globals, **kwargs)


@dispatcher
class RegexpDispatcher(object):
    def __init__(self, app_list, name='RegexpDispatcher'):
        self.name = name
        self.log = logging.getLogger('frontik.dispatcher.{0}'.format(name))
        self.log.info('initializing...')

        def parse_conf(pattern, app, parse=lambda x: [x]):
            try:
                app._initialize()
            except AttributeError:
                # it means that app is not dispatcher -> nothing to _initialize
                pass
            return re.compile(pattern), app, parse

        self.apps = [parse_conf(*app_conf) for app_conf in app_list]

    def __call__(self, application, request, **kwargs):
        relative_url = get_to_dispatch(request, 'uri')
        self.log.info('requested url: %s (%s)', relative_url, request.uri)
        for pattern, app, parse in self.apps:

            match = pattern.match(relative_url)
            # app found
            if match:
                self.log.debug('using %s' % app)
                augment_request(request, match, parse)
                try:
                    return app(application, request, **kwargs)
                except tornado.web.HTTPError as e:
                    log.exception('%s. Tornado error, %s', app, e)
                    return tornado.web.ErrorHandler(application, request, e.status_code)
                except Exception as e:
                    log.exception('%s. Internal server error, %s', app, e)
                return tornado.web.ErrorHandler(application, request, status_code=500)

        self.log.error('match for request url "%s" not found', request.uri)
        return tornado.web.ErrorHandler(application, request, status_code=404)


def get_app(app_urls, tornado_settings=None):
    dispatcher = RegexpDispatcher(app_urls, 'root')
    dispatcher._initialize()

    if tornado_settings is None:
        tornado_settings = {}

    return tornado.web.Application([
        (r'/version/?', VersionHandler),
        (r'/status/?', StatusHandler),
        (r'/stop/?', StopHandler),
        (r'/types_count/?', CountTypesHandler),
        (r'/pdb/?', PdbHandler),
        (r'/ph_count/?', CountPageHandlerInstancesHandler),
        (r'/.*', dispatcher),
    ], **tornado_settings)
