import json
import logging
import re

import tornado.routing

from frontik.app import FrontikApplication
from frontik.handler import RedirectHandler
from frontik.loggers import bootstrap_logger
from frontik.options import options
from frontik.routing import get_application_404_handler_delegate
from tests.projects.test_app import config


class TestApplication(FrontikApplication):
    def __init__(self, **settings):
        options.sentry_dsn = 'http://secret@127.0.0.1:{}/2'.format(settings['port'])

        bootstrap_logger('custom_logger', logging.DEBUG, False)

        super().__init__(**settings)

    async def init(self):
        await super().init()

        self.http_client_factory.request_engine_builder.kafka_producer = TestKafkaProducer()

    def application_urls(self):
        return [('^/redirect', RedirectRouter()), *super().application_urls()]

    def application_config(self):
        return config

    def application_version_xml(self):
        return config.version


class TestKafkaProducer:
    def __init__(self) -> None:
        self.data: list[dict[str, dict]] = []
        self.request_id = None

    async def send(self, topic, value=None):
        json_data = json.loads(value)

        if json_data['requestId'] == self.request_id:
            self.data.append({topic: json_data})

    def enable_for_request_id(self, request_id):
        self.request_id = request_id

    def disable_and_get_data(self):
        self.request_id = None
        return self.data


class RedirectRouter(tornado.routing.Router):
    PERMANENT_REDIRECT_PATTERN = re.compile(r'^/redirect/permanent')
    TEMPORARY_REDIRECT_PATTERN = re.compile(r'^/redirect/temporary')

    def find_handler(self, request, **kwargs):
        application = kwargs['application']
        if self.PERMANENT_REDIRECT_PATTERN.match(request.uri):
            permanent = True
        elif self.TEMPORARY_REDIRECT_PATTERN.match(request.uri):
            permanent = False
        else:
            return get_application_404_handler_delegate(application, request)
        redirect_arguments = {'url': '/finish?foo=bar', 'permanent': permanent}
        return application.get_handler_delegate(request, RedirectHandler, redirect_arguments)
