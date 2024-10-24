from fastapi.responses import JSONResponse

from frontik.routing import router


@router.get('/v1/kv/upstream/')
async def get_page():
    return JSONResponse([{'Value': None, 'CreateIndex': 1, 'ModifyIndex': 1}], headers={'X-Consul-Index': '1'})


@router.put('/v1/kv/upstream/')
async def put_page():
    pass


@router.post('/v1/kv/upstream/')
async def post_page():
    pass
