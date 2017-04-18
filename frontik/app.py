# coding=utf-8

import importlib
import json
import time
from functools import partial

from lxml import etree
from tornado.concurrent import Future
from tornado.httpclient import AsyncHTTPClient
from tornado.options import options
from tornado.stack_context import StackContext
from tornado.web import Application, RequestHandler

import frontik.producers.json_producer
import frontik.producers.xml_producer
from frontik.debug import DebugTransform
from frontik.handler import ErrorHandler
from frontik.loggers import bootstrap_app_loggers, request
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
            etree.tostring(get_frontik_and_apps_versions(self.application), encoding='utf-8', xml_declaration=True)
        )


class StatusHandler(RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.finish(self.application.get_current_status())


class FrontikApplication(Application):
    request_id = 0

    class DefaultConfig(object):
        pass

    def __init__(self, **settings):
        self.start_time = time.time()

        tornado_settings = settings.get('tornado_settings')
        if tornado_settings is None:
            tornado_settings = {}

        self.app_settings = settings
        self.config = self.application_config()
        self.app = settings.get('app')

        self.xml = frontik.producers.xml_producer.XMLProducerFactory(self)
        self.json = frontik.producers.json_producer.JsonProducerFactory(self)

        AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient', max_clients=options.max_http_clients)
        self.http_client = self.curl_http_client = AsyncHTTPClient()

        self.router = FrontikRouter(self)
        self.loggers_initializers = bootstrap_app_loggers(self)

        super(FrontikApplication, self).__init__([
            (r'/version/?', VersionHandler),
            (r'/status/?', StatusHandler),
            (r'.*', self.router),
        ], **tornado_settings)

        self.transforms.insert(0, partial(DebugTransform, self))

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

    def application_404_handler(self, request):
        return ErrorHandler, {'status_code': 404}

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

    def get_current_status(self):
        cur_uptime = time.time() - self.start_time
        if cur_uptime < 60:
            uptime_value = '{:.2f} seconds'.format(cur_uptime)
        elif cur_uptime < 3600:
            uptime_value = '{:.2f} minutes'.format(cur_uptime / 60)
        else:
            uptime_value = '{:.2f} hours and {:.2f} minutes'.format(cur_uptime / 3600, (cur_uptime % 3600) / 60)

        return {
            'uptime': uptime_value,
            'workers': {
                'total': options.max_http_clients,
                'free':  len(self.curl_http_client._free_list)
            }
        }

    def log_request(self, handler):
        super(FrontikApplication, self).log_request(handler)
        if isinstance(getattr(handler, 'log', None), request.RequestLogger):
            handler.log.stage_tag('flush')
            handler.log.log_stages(handler.get_status())
