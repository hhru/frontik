from tornado import gen

from frontik.handler import PageHandler


class Page(PageHandler):
    def get_page(self):
        self.get_kafka_producer('infrastructure').enable_for_request_id(self.request_id)

        yield self.post_url(self.request.host, self.request.uri)
        yield gen.sleep(0.1)

        self.json.put(*self.get_kafka_producer('infrastructure').disable_and_get_data())

    def post_page(self):
        self.set_status(500)
