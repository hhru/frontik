import asyncio

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from frontik.dependencies import HttpClientT
from frontik.routing import router


@router.get('/kafka')
async def get_page(http_client: HttpClientT, request: Request) -> JSONResponse:
    rid = request.scope['tornado_request'].request_id
    http_client.request_engine_builder.kafka_producer.enable_for_request_id(rid)

    await http_client.post_url(request.headers.get('host'), request.url.path)
    await asyncio.sleep(0.1)

    return JSONResponse(*http_client.request_engine_builder.kafka_producer.disable_and_get_data())


@router.post('/kafka')
async def post_page():
    raise HTTPException(500)
