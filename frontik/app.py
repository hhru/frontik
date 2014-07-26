# coding=utf-8

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

from frontik import frontik_logging
from frontik.globals import global_stats
from frontik.handler import ApplicationGlobals, PageHandler
import frontik.magic_imp
import frontik.xml_util

app_logger = logging.getLogger('frontik.app')


def _get_apps_versions():
    app_versions = etree.Element('applications')

    for path, app in options.urls:
        app_info = etree.Element('application', name=repr(app), path=path)
        try:
            application = app.app_globals.config.version
            app_info.extend(list(application))
        except:
            etree.SubElement(app_info, 'version').text = 'app doesn''t support version'

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
        app_logger.info('requested shutdown')
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


class FileMappingDispatcher(object):
    def __init__(self, module, handler_404=None):
        self.module = module
        self.name = module.__name__
        self.handler_404 = handler_404
        app_logger.info('initialized %r', self)

    def __call__(self, application, request, logger, **kwargs):
        page_module_name = 'pages.' + '.'.join(filter(None, get_to_dispatch(request, 'path').strip('/').split('/')))
        logger.debug('page module: %s', page_module_name)

        try:
            page_module = self.module.frontik_import(page_module_name)
            logger.debug('using %s from %s', (self.name, page_module_name), page_module.__file__)
        except ImportError:
            logger.exception('%s module not found', (self.name, page_module_name))
            if self.handler_404 is not None:
                return self.handler_404
            return tornado.web.ErrorHandler(application, request, status_code=404, logger=logger)
        except AttributeError:
            logger.exception('%s is not frontik application module (no "frontik_import" method)', self.name)
            return tornado.web.ErrorHandler(application, request, status_code=500, logger=logger)
        except:
            logger.exception('error while importing %s module', (self.name, page_module_name))
            return tornado.web.ErrorHandler(application, request, status_code=500, logger=logger)

        if not hasattr(page_module, 'Page'):
            logger.error('%s. Page class not found', page_module_name)
            return tornado.web.ErrorHandler(application, request, status_code=404, logger=logger)

        return page_module.Page(application, request, logger=logger, **kwargs)

    def __repr__(self):
        return 'FileMappingDispatcher({}, handler_404={})'.format(self.name, self.handler_404)

# Deprecated synonym
Map2ModuleName = FileMappingDispatcher


class App(object):
    class DefaultConfig(object):
        pass

    def __init__(self, name, root, config=None):
        self.name = name
        self.root = root
        self.config = config

    def initialize_app(self):
        app_logger.info('initializing %r', self)
        self.importer = frontik.magic_imp.FrontikAppImporter(self.name, self.root)
        self.init_app_package(self.name, self.config)
        self.app_globals = ApplicationGlobals(self.module)

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
                app_logger.warn('no config.py file, using empty default')

        if not hasattr(self.module.config, 'urls'):
            self.module.config.urls = [('', Map2ModuleName(self.pages_module))]

        self.dispatcher = RegexpDispatcher(self.module.config.urls, self.module.__name__)

    def __call__(self, application, request, logger, **kwargs):
        logger.info('requested app url: %s (%s)', get_to_dispatch(request, 'uri'), request.uri)
        return self.dispatcher(application, request, logger=logger, app_globals=self.app_globals, **kwargs)

    def __repr__(self):
        return 'App({})'.format(self.name)


class RegexpDispatcher(object):
    def __init__(self, app_list, name='RegexpDispatcher'):
        self.name = name

        def parse_conf(pattern, app, parse=lambda x: [x]):
            if hasattr(app, 'initialize_app'):
                app.initialize_app()
            return re.compile(pattern), app, parse

        self.apps = [parse_conf(*app_conf) for app_conf in app_list]
        app_logger.info('initialized %r', self)

    def __call__(self, application, request, logger, **kwargs):
        relative_url = get_to_dispatch(request, 'uri')
        logger.info('requested url: %s (%s)', relative_url, request.uri)
        for pattern, app, parse in self.apps:

            match = pattern.match(relative_url)
            # app found
            if match:
                logger.debug('using %r', app)
                augment_request(request, match, parse)
                try:
                    return app(application, request, logger, **kwargs)
                except tornado.web.HTTPError as e:
                    logger.exception('Tornado error: %s in %r', e, app)
                    return tornado.web.ErrorHandler(application, request, status_code=e.status_code, logger=logger)
                except Exception as e:
                    logger.exception('Internal server error: %s in %r', e, app)
                return tornado.web.ErrorHandler(application, request, status_code=500, logger=logger)

        logger.error('match for request url "%s" not found', request.uri)
        return tornado.web.ErrorHandler(application, request, status_code=404, logger=logger)

    def __repr__(self):
        return 'RegexpDispatcher({} routes)'.format(len(self.apps))


def get_app(app_urls, tornado_settings=None):
    dispatcher = RegexpDispatcher(app_urls, 'root')

    def root_dipatcher(app, request, **kwargs):
        request_id = request.headers.get('X-Request-Id', str(global_stats.next_request_id()))
        request_logger = frontik_logging.RequestLogger(request, request_id)
        return dispatcher(app, request, logger=request_logger, request_id=request_id, **kwargs)

    if tornado_settings is None:
        tornado_settings = {}

    return tornado.web.Application([
        (r'/version/?', VersionHandler),
        (r'/status/?', StatusHandler),
        (r'/stop/?', StopHandler),
        (r'/types_count/?', CountTypesHandler),
        (r'/pdb/?', PdbHandler),
        (r'/ph_count/?', CountPageHandlerInstancesHandler),
        (r'/.*', root_dipatcher),
    ], **tornado_settings)
