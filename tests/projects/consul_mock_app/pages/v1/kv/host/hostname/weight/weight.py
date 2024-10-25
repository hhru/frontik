from fastapi.responses import JSONResponse

from frontik.routing import regex_router


@regex_router.get(r'^/v1/kv/host/([a-zA-Z\-_0-9\.:\-]+)/weight')
async def get_page():
    return JSONResponse([{'Value': 'NTU=', 'CreateIndex': 1, 'ModifyIndex': 1}], headers={'X-Consul-Index': '1'})


@regex_router.put(r'^/v1/kv/host/([a-zA-Z\-_0-9\.:\-]+)/weight')
async def put_page():
    pass


@regex_router.post(r'^/v1/kv/host/([a-zA-Z\-_0-9\.:\-]+)/weight')
async def post_page():
    pass
