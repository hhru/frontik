import asyncio

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/kafka', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    request_engine_builder = handler.application.http_client_factory.request_engine_builder
    request_engine_builder.kafka_producer.enable_for_request_id(handler.request_id)

    await handler.post_url(handler.get_header('host'), handler.path)
    await asyncio.sleep(0.1)

    handler.json.put(*request_engine_builder.kafka_producer.disable_and_get_data())


@router.post('/kafka', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_status(500)
