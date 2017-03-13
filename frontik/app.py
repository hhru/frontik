# coding=utf-8

import importlib
import logging
import os
import re
import time
from functools import partial

import tornado.autoreload
import tornado.ioloop
import tornado.web
from lxml import etree
from tornado.concurrent import Future
from tornado.httpclient import AsyncHTTPClient
from tornado.options import options
from tornado.stack_context import StackContext

import frontik.loggers
import frontik.producers.json_producer
import frontik.producers.xml_producer
from frontik.compat import iteritems
from frontik.handler import ErrorHandler
from frontik.loggers.request import RequestLogger
from frontik.request_context import RequestContext
from frontik.util import reverse_regex_named_groups

app_logger = logging.getLogger('frontik.app')

MAX_MODULE_NAME_LENGTH = os.pathconf('/', 'PC_PATH_MAX') - 1


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

        if len(page_module_name) > MAX_MODULE_NAME_LENGTH:
            logger.info('page module name exceeds PATH_MAX (%s), using 404 page', MAX_MODULE_NAME_LENGTH)
            return self.handle_404(application, request, logger, **kwargs)

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
    def __init__(self, handlers, *args, **kwargs):  # *args and **kwargs are left for compatibility
        self.handlers = []
        self.handler_names = {}

        for handler_spec in handlers:
            if len(handler_spec) > 2:
                pattern, handler, handler_name = handler_spec
            else:
                handler_name = None
                pattern, handler = handler_spec

            self.handlers.append((re.compile(pattern), handler))

            if handler_name is not None:
                self.handler_names[handler_name] = pattern

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
                except Exception as e:
                    logger.exception('error handling request: %s in %r', e, handler)
                    return ErrorHandler(application, request, logger, status_code=500, **kwargs)

        logger.error('match for request url "%s" not found', request.uri)
        return ErrorHandler(application, request, logger, status_code=404, **kwargs)

    def reverse(self, name, *args, **kwargs):
        if name not in self.handler_names:
            raise KeyError('%s not found in named urls' % name)

        return reverse_regex_named_groups(self.handler_names[name], *args, **kwargs)

    def __repr__(self):
        return '{}.{}(<{} routes>)'.format(__package__, self.__class__.__name__, len(self.handlers))


def app_dispatcher(tornado_app, request, **kwargs):
    request_id = request.headers.get('X-Request-Id')
    context_request_id = RequestContext.get('request_id')

    if context_request_id is None or (request_id is not None and request_id != context_request_id):
        logging.getLogger('frontik.request_handler').warning(
            'RequestContext is inconsistent: %s != %s', context_request_id, request_id
        )

        if request_id is None:
            request_id = FrontikApplication.next_request_id()
    else:
        request_id = context_request_id

    request_logger = RequestLogger(request, request_id)
    return tornado_app.dispatcher(tornado_app, request, request_logger, **kwargs)


class FrontikApplication(tornado.web.Application):
    request_id = 0

    class DefaultConfig(object):
        pass

    def __init__(self, **settings):
        self.start_time = time.time()

        tornado_settings = settings.get('tornado_settings')
        if tornado_settings is None:
            tornado_settings = {}

        super(FrontikApplication, self).__init__([
            (r'/version/?', VersionHandler),
            (r'/status/?', StatusHandler),
            (r'.*', app_dispatcher),
        ], **tornado_settings)

        self.app_settings = settings
        self.config = self.application_config()
        self.app = settings.get('app')

        self.xml = frontik.producers.xml_producer.XMLProducerFactory(self)
        self.json = frontik.producers.json_producer.JsonProducerFactory(self)

        AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient', max_clients=options.max_http_clients)
        self.http_client = self.curl_http_client = AsyncHTTPClient()

        self.dispatcher = RegexpDispatcher(self.application_urls(), self.app)
        self.loggers_initializers = frontik.loggers.bootstrap_app_loggers(self)

    def __call__(self, request):
        request_id = request.headers.get('X-Request-Id')
        if request_id is None:
            request_id = FrontikApplication.next_request_id()

        with StackContext(partial(RequestContext, {'request_id': request_id})):
            return super(FrontikApplication, self).__call__(request)

    def reverse_url(self, name, *args, **kwargs):
        return self.dispatcher.reverse(name, *args, **kwargs)

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
