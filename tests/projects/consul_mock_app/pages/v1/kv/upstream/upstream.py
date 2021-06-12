import json

from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        self.set_header('X-Consul-Index', 1)
        self.text = json.dumps([{'Value': None, 'CreateIndex': 1, 'ModifyIndex': 1}])
        self.set_status(200)

    async def put_page(self):
        self.set_status(200)

    async def post_page(self):
        self.set_status(200)
