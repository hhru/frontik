import pytest

from frontik.testing import FrontikTestBase
from tests.instances import frontik_test_app
import asyncio
from frontik.routing import router
from fastapi import HTTPException
from frontik.dependencies import HttpClientT
from fastapi import Request
from fastapi.responses import JSONResponse


@router.get('/kafka')
async def get_page(http_client: HttpClientT, request: Request):
    rid = request.scope['tornado_request'].request_id
    http_client.request_engine_builder.kafka_producer.enable_for_request_id(rid)

    await http_client.post_url(request.headers.get('host'), request.url.path)
    await asyncio.sleep(0.1)

    return JSONResponse(*http_client.request_engine_builder.kafka_producer.disable_and_get_data())


@router.post('/kafka')
async def post_page():
    raise HTTPException(500)
