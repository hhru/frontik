# coding=utf-8

import importlib
import logging
import re
import time
from lxml import etree

import tornado.autoreload
from tornado.concurrent import Future
import tornado.curl_httpclient
import tornado.ioloop
from tornado.options import options
import tornado.web

from frontik.compat import iteritems
from frontik.handler import ErrorHandler
import frontik.loggers
from frontik.loggers.request import RequestLogger
import frontik.producers.json_producer
import frontik.producers.xml_producer

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
        self.set_header('Content-Type', 'application/json; charset=UTF-8')

        cur_uptime = time.time() - self.application.start_time
        if cur_uptime < 60:
            uptime_value = '{:.2f} seconds'.format(cur_uptime)
        elif cur_uptime < 3600:
            uptime_value = '{:.2f} minutes'.format(cur_uptime / 60)
        else:
            uptime_value = '{:.2f} hours and {:.2f} minutes'.format(cur_uptime / 3600, (cur_uptime % 3600) / 60)

        result = {
            'uptime': uptime_value,
            'workers': {
                'total': tornado.options.options.max_http_clients,
                'free':  len(self.application.curl_http_client._free_list)
            }
        }

        self.finish(result)


def extend_request_arguments(request, match):
    arguments = match.groupdict()
    for name, value in iteritems(arguments):
        if value:
            request.arguments.setdefault(name, []).append(value)


class FileMappingDispatcher(object):
    def __init__(self, module, handler_404=None):
        self.name = module.__name__
        self.handler_404 = handler_404
        app_logger.info('initialized %r', self)

    def __call__(self, application, request, logger, **kwargs):
        url_parts = request.path.strip('/').split('/')

        if any('.' in part for part in url_parts):
            logger.info('url contains "." character, using 404 page')
            return self.handle_404(application, request, logger, **kwargs)

        page_name = '.'.join(filter(None, url_parts))
        page_module_name = '.'.join(filter(None, (self.name, page_name)))
        logger.debug('page module: %s', page_module_name)

        try:
            page_module = importlib.import_module(page_module_name)
            logger.debug('using %s from %s', page_module_name, page_module.__file__)
        except ImportError:
            logger.warning('%s module not found', (self.name, page_module_name))
            return self.handle_404(application, request, logger, **kwargs)
        except:
            logger.exception('error while importing %s module', page_module_name)
            return ErrorHandler(application, request, logger, status_code=500, **kwargs)

        if not hasattr(page_module, 'Page'):
            logger.error('%s.Page class not found', page_module_name)
            return self.handle_404(application, request, logger, **kwargs)

        return page_module.Page(application, request, logger, **kwargs)

    def __repr__(self):
        return '{}.{}(<{}, handler_404={}>)'.format(__package__, self.__class__.__name__, self.name, self.handler_404)

    def handle_404(self, application, request, logger, **kwargs):
        if self.handler_404 is not None:
            return self.handler_404(application, request, logger, **kwargs)
        return ErrorHandler(application, request, logger, status_code=404, **kwargs)


class RegexpDispatcher(object):
    def __init__(self, app_list, name='RegexpDispatcher'):
        self.name = name
        self.handlers = [(re.compile(pattern), handler) for pattern, handler in app_list]

        app_logger.info('initialized %r', self)

    def __call__(self, application, request, logger, **kwargs):
        logger.info('requested url: %s', request.uri)

        for pattern, handler in self.handlers:
            match = pattern.match(request.uri)
            if match:
                logger.debug('using %r', handler)
                extend_request_arguments(request, match)
                try:
                    return handler(application, request, logger, **kwargs)
                except tornado.web.HTTPError as e:
                    logger.exception('tornado error: %s in %r', e, handler)
                    return ErrorHandler(application, request, logger, status_code=e.status_code, **kwargs)
                except Exception as e:
                    logger.exception('error handling request: %s in %r', e, handler)
                    return ErrorHandler(application, request, logger, status_code=500, **kwargs)

        logger.error('match for request url "%s" not found', request.uri)
        return ErrorHandler(application, request, logger, status_code=404, **kwargs)

    def __repr__(self):
        return '{}.{}(<{} routes>)'.format(__package__, self.__class__.__name__, len(self.handlers))


def app_dispatcher(tornado_app, request, **kwargs):
    request_id = request.headers.get('X-Request-Id', FrontikApplication.next_request_id())
    request_logger = RequestLogger(request, request_id)
    return tornado_app.dispatcher(tornado_app, request, request_logger, request_id=request_id, **kwargs)


class FrontikApplication(tornado.web.Application):
    request_id = 0

    class DefaultConfig(object):
        pass

    def __init__(self, **settings):
        tornado_settings = settings.get('tornado_settings')

        if tornado_settings is None:
            tornado_settings = {}

        self.start_time = time.time()

        super(FrontikApplication, self).__init__([
            (r'/version/?', VersionHandler),
            (r'/status/?', StatusHandler),
            (r'.*', app_dispatcher),
        ], **tornado_settings)

        self.app_settings = settings
        self.config = self.application_config()
        self.app = settings.get('app')
        self.xml = frontik.producers.xml_producer.ApplicationXMLGlobals(self.config)
        self.json = frontik.producers.json_producer.ApplicationJsonGlobals(self.config)
        self.curl_http_client = tornado.curl_httpclient.CurlAsyncHTTPClient(
            max_clients=tornado.options.options.max_http_clients)
        self.dispatcher = RegexpDispatcher(self.application_urls(), self.app)
        self.loggers_initializers = frontik.loggers.bootstrap_app_loggers(self)

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

    def init_async(self):
        init_future = Future()
        init_future.set_result(None)
        return init_future

    @staticmethod
    def next_request_id():
        FrontikApplication.request_id += 1
        return str(FrontikApplication.request_id)

# Temporary for backward compatibility
App = FrontikApplication
