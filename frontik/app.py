# coding=utf-8

import importlib
import logging
import re
import time

from lxml import etree
import tornado.autoreload
import tornado.web
import tornado.ioloop
from tornado.options import options

from frontik import frontik_logging
from frontik.globals import global_stats
from frontik.handler import ApplicationGlobals, BaseHandler, ErrorHandler

app_logger = logging.getLogger('frontik.app')


def _get_apps_versions():
    app_info = etree.Element('application', name=options.app)

    try:
        app_config = importlib.import_module('{}.config'.format(options.app))
        app_info.extend(list(app_config.version))
    except:
        etree.SubElement(app_info, 'version').text = 'unknown'

    return app_info


def get_frontik_and_apps_versions():
    from frontik.version import version
    import simplejson
    import sys
    import tornado

    versions = etree.Element('versions')
    etree.SubElement(versions, 'frontik').text = version
    etree.SubElement(versions, 'tornado').text = tornado.version
    etree.SubElement(versions, 'lxml.etree.LXML').text = '.'.join(str(x) for x in etree.LXML_VERSION)
    etree.SubElement(versions, 'lxml.etree.LIBXML').text = '.'.join(str(x) for x in etree.LIBXML_VERSION)
    etree.SubElement(versions, 'lxml.etree.LIBXSLT').text = '.'.join(str(x) for x in etree.LIBXSLT_VERSION)
    etree.SubElement(versions, 'simplejson').text = simplejson.__version__
    etree.SubElement(versions, 'python').text = sys.version.replace('\n', '')
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

        handlers = tuple(i for i in gc.get_objects() if isinstance(i, BaseHandler))

        self.finish(
            '{0}\n{1}'.format(len(handlers), [i for i in gc.get_referrers(*handlers) if i is not handlers])
        )


class CountTypesHandler(tornado.web.RequestHandler):
    def get(self):
        import gc
        from collections import defaultdict

        counts = defaultdict(int)
        for o in gc.get_objects():
            counts[type(o)] += 1

        for k, v in sorted(counts.items(), key=lambda x: x[0]):
            self.write('%s\t%s\n' % (v, k))


def get_rewritten_request_attribute(request, field):
    return getattr(request, 're_' + field, getattr(request, field))


def set_rewritten_request_attribute(request, field, value):
    setattr(request, 're_' + field, value)


get_to_dispatch = get_rewritten_request_attribute  # Old aliases


def set_to_dispatch(request, value, field='path'):
    set_rewritten_request_attribute(request, field, value)


def extend_request_arguments(request, match, parse_function):
    arguments = match.groupdict()
    for name, value in arguments.iteritems():
        if value:
            request.arguments.setdefault(name, []).extend(parse_function(value))

# Deprecated, remove after backwards-incompatible code is deleted

import imp
import sys

import frontik.magic_imp


class FileMappingDispatcher(object):
    def __init__(self, module, handler_404=None):
        self.module = module
        self.name = module.__name__
        self.handler_404 = handler_404
        app_logger.info('initialized %r', self)

    def __call__(self, application, request, logger, **kwargs):
        url_parts = get_rewritten_request_attribute(request, 'path').strip('/').split('/')
        page_module_name = 'pages.' + '.'.join(filter(None, url_parts))
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
        return '{}.{}(<{}, handler_404={}>)'.format(__package__, self.__class__.__name__, self.name, self.handler_404)


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
                    tornado.autoreload.watch(filename)
            except ImportError:
                self.module.config = App.DefaultConfig()
                app_logger.warning('no config.py file, using empty default')

        if not hasattr(self.module.config, 'urls'):
            self.module.config.urls = [('', FileMappingDispatcher(self.pages_module))]

        self.app_globals = ApplicationGlobals(self.module.config)
        self.dispatcher = RegexpDispatcher(self.module.config.urls, self.module.__name__)

    def __call__(self, application, request, logger, **kwargs):
        return self.dispatcher(application, request, logger=logger, app_globals=self.app_globals, **kwargs)

    def __repr__(self):
        return '{}.{}({})'.format(__package__, self.__class__.__name__, self.name)


class NewFileMappingDispatcher(object):
    def __init__(self, module, handler_404=None):
        self.name = module.__name__
        self.handler_404 = handler_404
        app_logger.info('initialized %r', self)

    def __call__(self, application, request, logger, **kwargs):
        url_parts = get_rewritten_request_attribute(request, 'path').strip('/').split('/')
        page_name = '.'.join(filter(None, url_parts))
        page_module_name = '.'.join(filter(None, (self.name, page_name)))
        logger.debug('page module: %s', page_module_name)

        try:
            page_module = importlib.import_module(page_module_name)
            logger.debug('using %s from %s', page_module_name, page_module.__file__)
        except ImportError:
            logger.exception('%s module not found', (self.name, page_module_name))
            if self.handler_404 is not None:
                return self.handler_404(application, request, logger, **kwargs)
            return ErrorHandler(application, request, logger, status_code=404, **kwargs)
        except:
            logger.exception('error while importing %s module', page_module_name)
            return ErrorHandler(application, request, logger, status_code=500, **kwargs)

        if not hasattr(page_module, 'Page'):
            logger.error('%s.Page class not found', page_module_name)
            return ErrorHandler(application, request, logger, status_code=404, **kwargs)

        return page_module.Page(application, request, logger, **kwargs)

    def __repr__(self):
        return '{}.{}(<{}, handler_404={}>)'.format(__package__, self.__class__.__name__, self.name, self.handler_404)


class NewApp(object):
    class DefaultConfig(object):
        pass

    def __init__(self, module, config=None):
        self.module = module
        self.config = config

        app_logger.info('initializing %r', self)

        if self.config is None:
            try:
                self.config = importlib.import_module('{}.config'.format(self.module))
                tornado.autoreload.watch(self.config.__file__)
            except ImportError:
                self.config = NewApp.DefaultConfig()
                app_logger.warning('no config.py file, using empty default')

        if not hasattr(self.config, 'urls'):
            self.config.urls = [
                ('', NewFileMappingDispatcher(importlib.import_module('{}.pages'.format(self.module))))
            ]

        self.app_globals = ApplicationGlobals(self.config)
        self.dispatcher = RegexpDispatcher(self.config.urls, self.module)

    def __call__(self, application, request, logger, **kwargs):
        return self.dispatcher(application, request, logger, app_globals=self.app_globals, **kwargs)

    def __repr__(self):
        return '{}.{}({})'.format(__package__, self.__class__.__name__, self.module)


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
        relative_url = get_rewritten_request_attribute(request, 'uri')
        logger.info('requested url: %s (%s)', relative_url, request.uri)

        for pattern, app, parse in self.apps:
            match = pattern.match(relative_url)
            if match:
                logger.debug('using %r', app)
                extend_request_arguments(request, match, parse)
                try:
                    return app(application, request, logger, **kwargs)
                except tornado.web.HTTPError as e:
                    logger.exception('tornado error: %s in %r', e, app)
                    return ErrorHandler(application, request, logger, status_code=e.status_code, **kwargs)
                except Exception as e:
                    logger.exception('error handling request: %s in %r', e, app)
                    return ErrorHandler(application, request, logger, status_code=500, **kwargs)

        logger.error('match for request url "%s" not found', request.uri)
        return ErrorHandler(application, request, logger, status_code=404, **kwargs)

    def __repr__(self):
        return '{}.{}(<{} routes>)'.format(__package__, self.__class__.__name__, len(self.apps))


def get_tornado_app(app_root_url, frontik_app, tornado_settings=None):
    def app_dispatcher(tornado_app, request, **kwargs):
        request_id = request.headers.get('X-Request-Id', str(global_stats.next_request_id()))
        request_logger = frontik_logging.RequestLogger(request, request_id)

        def add_leading_slash(value):
            return value if value.startswith('/') else '/' + value

        app_root_url_len = len(options.app_root_url)
        set_rewritten_request_attribute(request, 'uri', add_leading_slash(request.uri[app_root_url_len:]))
        set_rewritten_request_attribute(request, 'path', add_leading_slash(request.path[app_root_url_len:]))

        return frontik_app(tornado_app, request, request_logger, request_id=request_id, **kwargs)

    if tornado_settings is None:
        tornado_settings = {}

    return tornado.web.Application([
        (r'/version/?', VersionHandler),
        (r'/status/?', StatusHandler),
        (r'/stop/?', StopHandler),
        (r'/types_count/?', CountTypesHandler),
        (r'/pdb/?', PdbHandler),
        (r'/ph_count/?', CountPageHandlerInstancesHandler),
        (r'{}.*'.format(app_root_url), app_dispatcher),
    ], **tornado_settings)
