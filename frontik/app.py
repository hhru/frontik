import importlib
import socket
import sys
import time
import traceback
from functools import partial
from typing import TYPE_CHECKING

import pycurl
import tornado
from lxml import etree
from tornado.options import options
from tornado.stack_context import StackContext
from tornado.web import Application, RequestHandler

import frontik.producers.json_producer
import frontik.producers.xml_producer
from frontik import integrations, media_types, request_context
from frontik.debug import DebugTransform
from frontik.handler import ErrorHandler
from frontik.http_client import HttpClientFactory
from frontik.loggers import CUSTOM_JSON_EXTRA, JSON_REQUESTS_LOGGER
from frontik.routing import FileMappingRouter, FrontikRouter
from frontik.service_discovery import get_async_service_discovery
from frontik.version import version as frontik_version

if TYPE_CHECKING:
    from typing import Optional

    from aiokafka import AIOKafkaProducer
    from tornado.httputil import HTTPServerRequest

    from frontik.integrations.sentry import SentryLogger


def get_frontik_and_apps_versions(application):
    versions = etree.Element('versions')

    etree.SubElement(versions, 'frontik').text = frontik_version
    etree.SubElement(versions, 'tornado').text = tornado.version
    etree.SubElement(versions, 'lxml.etree.LXML').text = '.'.join(str(x) for x in etree.LXML_VERSION)
    etree.SubElement(versions, 'lxml.etree.LIBXML').text = '.'.join(str(x) for x in etree.LIBXML_VERSION)
    etree.SubElement(versions, 'lxml.etree.LIBXSLT').text = '.'.join(str(x) for x in etree.LIBXSLT_VERSION)
    etree.SubElement(versions, 'pycurl').text = pycurl.version
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
        self.set_header('Content-Type', media_types.APPLICATION_JSON)
        self.finish(self.application.get_current_status())


class PydevdHandler(RequestHandler):
    def get(self):
        if hasattr(sys, 'gettrace') and sys.gettrace() is not None:
            self.already_tracing_page()
            return

        try:
            debugger_ip = self.get_argument('debugger_ip', self.request.remote_ip)
            debugger_port = self.get_argument('debugger_port', '32223')
            self.settrace(debugger_ip, int(debugger_port))
            self.trace_page(debugger_ip, debugger_port)

        except BaseException:
            self.error_page()

    def settrace(self, debugger_ip, debugger_port):
        import pydevd
        pydevd.settrace(debugger_ip, port=debugger_port, stdoutToServer=True, stderrToServer=True, suspend=False)

    def trace_page(self, ip, port):
        self.set_header('Content-Type', media_types.TEXT_PLAIN)
        self.finish(f'Connected to debug server at {ip}:{port}')

    def already_tracing_page(self):
        self.set_header('Content-Type', media_types.TEXT_PLAIN)
        self.finish('App is already in tracing mode, try to restart service')

    def error_page(self):
        self.set_header('Content-Type', media_types.TEXT_PLAIN)
        self.finish(traceback.format_exc())


class FrontikApplication(Application):
    request_id = 0

    class DefaultConfig:
        pass

    def __init__(self, **settings):
        self.start_time = time.time()

        tornado_settings = settings.get('tornado_settings')
        if tornado_settings is None:
            tornado_settings = {}

        self.config = self.application_config()
        self.app = settings.get('app')
        self.app_module = settings.get('app_module')
        self.app_root = settings.get('app_root')

        self.xml = frontik.producers.xml_producer.XMLProducerFactory(self)
        self.json = frontik.producers.json_producer.JsonProducerFactory(self)

        self.service_discovery_client = None
        self.http_client_factory = None

        self.router = FrontikRouter(self)

        core_handlers = [
            (r'/version/?', VersionHandler),
            (r'/status/?', StatusHandler),
            (r'.*', self.router),
        ]

        if options.debug:
            core_handlers.insert(0, (r'/pydevd/?', PydevdHandler))

        self.available_integrations = None

        super().__init__(core_handlers, **tornado_settings)

    def init_async(self):
        self.service_discovery_client = get_async_service_discovery(options, hostname=socket.gethostname())
        self.transforms.insert(0, partial(DebugTransform, self))

        self.http_client_factory = HttpClientFactory(self, getattr(self.config, 'http_upstreams', {}))

        self.available_integrations, default_init_futures = integrations.load_integrations(self)

        return default_init_futures

    def find_handler(self, request, **kwargs):
        request_id = request.headers.get('X-Request-Id')
        if request_id is None:
            request_id = FrontikApplication.next_request_id()

        context = partial(request_context.RequestContext, {'request': request, 'request_id': request_id})

        def wrapped_in_context(func):
            def wrapper(*args, **kwargs):
                token = request_context.initialize(request, request_id)

                try:
                    with StackContext(context):
                        return func(*args, **kwargs)
                finally:
                    request_context.reset(token)

            return wrapper

        delegate = wrapped_in_context(super().find_handler)(request, **kwargs)
        delegate.headers_received = wrapped_in_context(delegate.headers_received)
        delegate.data_received = wrapped_in_context(delegate.data_received)
        delegate.finish = wrapped_in_context(delegate.finish)
        delegate.on_connection_close = wrapped_in_context(delegate.on_connection_close)

        return delegate

    def reverse_url(self, name, *args, **kwargs):
        return self.router.reverse_url(name, *args, **kwargs)

    def application_urls(self):
        return [
            ('', FileMappingRouter(importlib.import_module(f'{self.app_module}.pages')))
        ]

    def application_404_handler(self, request):
        return ErrorHandler, {'status_code': 404}

    def application_config(self):
        return FrontikApplication.DefaultConfig()

    def application_version_xml(self):
        version = etree.Element('version')
        version.text = 'unknown'
        return [version]

    def application_version(self):
        return None

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
            'datacenter': options.datacenter,
            'workers': {
                'total': options.max_http_clients,
                'free': len(self.http_client_factory.tornado_http_client._free_list)
            }
        }

    def log_request(self, handler):
        if not options.log_json:
            super().log_request(handler)
            return

        request_time = int(1000.0 * handler.request.request_time())
        extra = {
            'ip': handler.request.remote_ip,
            'rid': request_context.get_request_id(),
            'status': handler.get_status(),
            'time': request_time,
            'method': handler.request.method,
            'uri': handler.request.uri,
        }

        handler_name = request_context.get_handler_name()
        if handler_name:
            extra['controller'] = handler_name

        JSON_REQUESTS_LOGGER.info('', extra={CUSTOM_JSON_EXTRA: extra})

    def get_kafka_producer(self, producer_name: str) -> 'Optional[AIOKafkaProducer]':  # pragma: no cover
        pass

    def get_sentry_logger(self, request: 'HTTPServerRequest') -> 'Optional[SentryLogger]':  # pragma: no cover
        pass
