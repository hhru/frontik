import json
import logging

from frontik.app import FrontikApplication
from frontik.loggers import bootstrap_logger
from tests.projects.test_app import config


class TestApplication(FrontikApplication):
    def __init__(self, app_module_name: str):
        bootstrap_logger('custom_logger', logging.DEBUG, False)
        super().__init__(app_module_name)

    async def init(self):
        await super().init()

        self.http_client_factory.request_engine_builder.kafka_producer = TestKafkaProducer()

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
