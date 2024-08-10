from fastapi import Request

from frontik.balancing_client import HttpClientT
from frontik.json_builder import JsonBuilderT
from frontik.routing import plain_router


@plain_router.get('/handler/delete')
async def get_page(request: Request, http_client: HttpClientT, json_builder: JsonBuilderT) -> None:
    result = await http_client.delete_url(
        'http://' + request.headers.get('host', ''), request.url.path, data={'data': 'true'}
    )
    if not result.failed:
        json_builder.put(result.data)


@plain_router.post('/handler/delete')
async def post_page(request: Request, http_client: HttpClientT, json_builder: JsonBuilderT) -> None:
    result = await http_client.delete_url('http://backend', request.url.path, fail_fast=True)
    if not result.failed:
        json_builder.put(result.data)


@plain_router.delete('/handler/delete')
async def delete_page(data: str, json_builder: JsonBuilderT) -> None:
    json_builder.put({'delete': data})
