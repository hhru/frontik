from fastapi.responses import JSONResponse

from frontik.routing import router


@router.get(r'/v1/kv/host/{path_param}/weight')
async def get_page():
    return JSONResponse([{'Value': 'NTU=', 'CreateIndex': 1, 'ModifyIndex': 1}], headers={'X-Consul-Index': '1'})


@router.put(r'/v1/kv/host/{path_param}/weight')
async def put_page():
    pass


@router.post(r'/v1/kv/host/{path_param}/weight')
async def post_page():
    pass
