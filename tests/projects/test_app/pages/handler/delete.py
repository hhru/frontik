from typing import Any

from fastapi import Request

from frontik.balancing_client import HttpClientT
from frontik.routing import plain_router


@plain_router.get('/handler/delete')
async def get_page(request: Request, http_client: HttpClientT) -> Any:
    result = await http_client.delete_url(
        'http://' + request.headers.get('host', ''), request.url.path, data={'data': 'true'}
    )
    return result.data


@plain_router.post('/handler/delete')
async def post_page(request: Request, http_client: HttpClientT) -> Any:
    result = await http_client.delete_url('http://backend', request.url.path, fail_fast=True)
    return result.data


@plain_router.delete('/handler/delete')
async def delete_page(data: str) -> dict:
    return {'delete': data}
