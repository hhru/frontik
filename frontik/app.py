# coding=utf-8

import importlib
import logging
import time
from functools import partial

import tornado.autoreload
import tornado.ioloop
from lxml import etree
from tornado.concurrent import Future
from tornado.httpclient import AsyncHTTPClient
from tornado.options import options
from tornado.stack_context import StackContext
from tornado.web import Application, asynchronous, RequestHandler

import frontik.loggers
import frontik.producers.json_producer
import frontik.producers.xml_producer
from frontik.loggers.request import RequestLogger
from frontik.request_context import RequestContext
from frontik.routing import FileMappingRouter, FrontikRouter


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


class VersionHandler(RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'text/xml')
        self.write(
            etree.tostring(get_frontik_and_apps_versions(self.application), encoding='utf-8', xml_declaration=True))


class StatusHandler(RequestHandler):

    @asynchronous
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
                'total': options.max_http_clients,
                'free':  len(self.application.curl_http_client._free_list)
            }
        }

        self.finish(result)


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
    return tornado_app.router(tornado_app, request, request_logger, **kwargs)


class FrontikApplication(Application):
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

        self.router = FrontikRouter(self.application_urls(), self.app)
        self.loggers_initializers = frontik.loggers.bootstrap_app_loggers(self)

    def __call__(self, request):
        request_id = request.headers.get('X-Request-Id')
        if request_id is None:
            request_id = FrontikApplication.next_request_id()

        with StackContext(partial(RequestContext, {'request_id': request_id})):
            return super(FrontikApplication, self).__call__(request)

    def reverse_url(self, name, *args, **kwargs):
        return self.router.reverse_url(name, *args, **kwargs)

    def application_urls(self):
        return [
            ('', FileMappingRouter(importlib.import_module('{}.pages'.format(self.app))))
        ]

    def application_404_handler(self):
        return None

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
