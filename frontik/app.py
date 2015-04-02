# coding=utf-8
import httplib

import importlib
import logging
import re
import time

from lxml import etree
import tornado.autoreload
import tornado.web
import tornado.ioloop
import tornado.curl_httpclient
from tornado.options import options

from frontik import frontik_logging
from frontik.globals import global_stats
import frontik.producers.json_producer
import frontik.producers.xml_producer
from frontik.handler import ErrorHandler
import frontik.sentry
from frontik.util import make_get_request

app_logger = logging.getLogger('frontik.app')


def get_frontik_and_apps_versions(application):
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
    etree.SubElement(versions, 'application', name=options.app).extend(application.application_version_xml())

    return versions


class VersionHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'text/xml')
        self.write(
            etree.tostring(get_frontik_and_apps_versions(self.application), encoding='utf-8', xml_declaration=True))


class StatusHandler(tornado.web.RequestHandler):

    @tornado.web.asynchronous
    def get(self):
        if self.get_argument('no_network_check', 'false') == 'true':
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
            self.finish(result)
        else:
            request = make_get_request(
                'http://{host}:{port}/status'.format(host='127.0.0.1' if options.host == '0.0.0.0' else options.host,
                                                     port=options.port),
                data={'no_network_check': 'true'},
                connect_timeout=0.5,
                request_timeout=0.5,
                follow_redirects=False
            )

            def _request_ready(result):
                if result.error is not None:
                    raise tornado.web.HTTPError(httplib.SERVICE_UNAVAILABLE)
                self.set_header('Content-Type', 'application/json; charset=UTF-8')
                self.finish(result.body)

            self.application.curl_http_client.fetch(request, callback=_request_ready)


class PdbHandler(tornado.web.RequestHandler):
    def get(self):
        import pdb
        pdb.set_trace()


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


def extend_request_arguments(request, match, parse_function):
    arguments = match.groupdict()
    for name, value in arguments.iteritems():
        if value:
            request.arguments.setdefault(name, []).extend(parse_function(value))


class FileMappingDispatcher(object):
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
            logger.warning('%s module not found', (self.name, page_module_name))
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


def app_dispatcher(tornado_app, request, **kwargs):
    request_id = request.headers.get('X-Request-Id', str(global_stats.next_request_id()))
    request_logger = frontik_logging.RequestLogger(request, request_id)

    def add_leading_slash(value):
        return value if value.startswith('/') else '/' + value

    app_root_url_len = len(options.app_root_url)
    set_rewritten_request_attribute(request, 'uri', add_leading_slash(request.uri[app_root_url_len:]))
    set_rewritten_request_attribute(request, 'path', add_leading_slash(request.path[app_root_url_len:]))

    return tornado_app.dispatcher(tornado_app, request, request_logger, request_id=request_id, **kwargs)


class FrontikApplication(tornado.web.Application):
    class DefaultConfig(object):
        pass

    def __init__(self, **settings):
        tornado_settings = settings.get('tornado_settings')

        if tornado_settings is None:
            tornado_settings = {}

        super(FrontikApplication, self).__init__([
            (r'/version/?', VersionHandler),
            (r'/status/?', StatusHandler),
            (r'/types_count/?', CountTypesHandler),
            (r'/pdb/?', PdbHandler),
            (r'{}.*'.format(settings.get('app_root_url')), app_dispatcher),
        ], **tornado_settings)

        self.config = self.application_config()
        self.app = settings.get('app')
        self.xml = frontik.producers.xml_producer.ApplicationXMLGlobals(self.config)
        self.json = frontik.producers.json_producer.ApplicationJsonGlobals(self.config)
        self.curl_http_client = tornado.curl_httpclient.CurlAsyncHTTPClient(max_clients=200)
        self.dispatcher = RegexpDispatcher(self.application_urls(), self.app)
        self.sentry_client = self._build_sentry_client(settings)

    def _build_sentry_client(self, settings):
        dsn = settings.get('sentry_dsn')
        if not dsn:
            return
        if not frontik.sentry.has_raven:
            app_logger.warning('sentry_dsn set but raven not avalaible')
            return
        return frontik.sentry.AsyncSentryClient(dsn=dsn, http_client=self.curl_http_client)

    def application_urls(self):
        return [
            ('', FileMappingDispatcher(importlib.import_module('{}.pages'.format(self.app))))
        ]

    def application_config(self):
        return FrontikApplication.DefaultConfig()

    def application_version_xml(self):
        version = etree.Element('version')
        version.text = 'unknown'
        return [version]

# Temporary for backward compatibility
App = FrontikApplication
