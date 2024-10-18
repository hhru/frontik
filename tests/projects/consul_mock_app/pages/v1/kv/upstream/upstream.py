import json

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/v1/kv/upstream/', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.set_header('X-Consul-Index', '1')
    handler.text = json.dumps([{'Value': None, 'CreateIndex': 1, 'ModifyIndex': 1}])
    handler.set_status(200)


@router.put('/v1/kv/upstream/', cls=PageHandler)
async def put_page(handler=get_current_handler()):
    handler.set_status(200)


@router.post('/v1/kv/upstream/', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_status(200)
