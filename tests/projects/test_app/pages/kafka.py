import json

from tornado import gen

from frontik.handler import PageHandler


class Page(PageHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)

        self._kafka_producer = TestKafkaProducer(self)
        self.get_kafka_producer = lambda _: self._kafka_producer

    def get_page(self):
        yield self.post_url(self.request.host, self.request.uri)
        yield gen.sleep(0.1)

    def post_page(self):
        self.set_status(500)


class TestKafkaProducer:
    def __init__(self, handler):
        self.handler = handler

    async def send(self, topic, value=None):
        self.handler.json.put({
            topic: json.loads(value)
        })
