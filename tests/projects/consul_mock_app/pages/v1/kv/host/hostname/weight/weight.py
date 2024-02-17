import json

from frontik.handler import PageHandler, router


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        self.set_header('X-Consul-Index', 1)
        self.text = json.dumps([{'Value': 'NTU=', 'CreateIndex': 1, 'ModifyIndex': 1}])
        self.set_status(200)

    @router.put()
    async def put_page(self):
        self.set_status(200)

    @router.post()
    async def post_page(self):
        self.set_status(200)
