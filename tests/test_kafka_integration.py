import asyncio
import json

import pytest
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from frontik.app import FrontikApplication
from frontik.dependencies import http_client
from frontik.options import options
from frontik.routing import router
from frontik.testing import FrontikTestBase


class KafkaProducerMock:
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


class KafkaApplication(FrontikApplication):
    async def init(self):
        await super().init()
        self.http_client_factory.request_engine_builder.kafka_producer = KafkaProducerMock()


@router.get('/kafka')
async def get_page(request: Request) -> JSONResponse:
    rid = request.scope['tornado_request'].request_id
    request.app.http_client_factory.request_engine_builder.kafka_producer.enable_for_request_id(rid)

    await http_client.post_url(request.headers.get('host'), request.url.path)
    await asyncio.sleep(0.1)

    return JSONResponse(*request.app.http_client_factory.request_engine_builder.kafka_producer.disable_and_get_data())


@router.post('/kafka')
async def post_page():
    raise HTTPException(500)


class TestKafkaIntegration(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        options.service_name = 'test_kafka_integration'
        return KafkaApplication()

    async def test_kafka(self):
        response_json = await self.fetch_json('/kafka')

        assert response_json['metrics_requests']['app'] == 'test_kafka_integration'
        assert response_json['metrics_requests']['dc'] == 'externalRequest'
        assert 'hostname' in response_json['metrics_requests']
        assert 'requestId' in response_json['metrics_requests']
        assert response_json['metrics_requests']['status'] == 500
        assert 'ts' in response_json['metrics_requests']
        assert 'upstream' in response_json['metrics_requests']
