import json

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import regex_router


@regex_router.get(r'^/v1/kv/host/([a-zA-Z\-_0-9\.:\-]+)/weight', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.set_header('X-Consul-Index', '1')
    handler.text = json.dumps([{'Value': 'NTU=', 'CreateIndex': 1, 'ModifyIndex': 1}])
    handler.set_status(200)


@regex_router.put(r'^/v1/kv/host/([a-zA-Z\-_0-9\.:\-]+)/weight', cls=PageHandler)
async def put_page(handler=get_current_handler()):
    handler.set_status(200)


@regex_router.post(r'^/v1/kv/host/([a-zA-Z\-_0-9\.:\-]+)/weight', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_status(200)
