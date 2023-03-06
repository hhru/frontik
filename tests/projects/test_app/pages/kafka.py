import asyncio

from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        request_engine_builder = self.application.http_client_factory.request_engine_builder
        request_engine_builder.kafka_producer.enable_for_request_id(self.request_id)

        await self.post_url(self.request.host, self.request.uri)
        await asyncio.sleep(0.1)

        self.json.put(*request_engine_builder.kafka_producer.disable_and_get_data())

    async def post_page(self):
        self.set_status(500)
