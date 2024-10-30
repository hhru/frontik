from http_client import HttpClient
from http_client.request_response import RequestResult

from frontik.dependencies import clients


async def get_url(*args, **kwargs) -> RequestResult:
    _http_client: HttpClient = clients.get().get('http_client')
    return await _http_client.get_url(*args, **kwargs)


async def head_url(*args, **kwargs) -> RequestResult:
    _http_client: HttpClient = clients.get().get('http_client')
    return await _http_client.head_url(*args, **kwargs)


async def post_url(*args, **kwargs) -> RequestResult:
    _http_client: HttpClient = clients.get().get('http_client')
    return await _http_client.post_url(*args, **kwargs)


async def put_url(*args, **kwargs) -> RequestResult:
    _http_client: HttpClient = clients.get().get('http_client')
    return await _http_client.put_url(*args, **kwargs)


async def delete_url(*args, **kwargs) -> RequestResult:
    _http_client: HttpClient = clients.get().get('http_client')
    return await _http_client.delete_url(*args, **kwargs)
