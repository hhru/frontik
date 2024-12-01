import asyncio

from fastapi import Request
from http_client.balancing import Upstream
from http_client.request_response import RequestResult

from frontik.dependencies import HttpClient
from frontik.routing import router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


@router.get('/requests_count')
async def get_page(request: Request, http_client: HttpClient) -> str:
    upstreams = request.app.service_discovery.get_upstreams_unsafe()
    requests_count_async = 'requests_count_async'
    upstreams[requests_count_async] = Upstream(requests_count_async, {}, [get_server(request, 'normal')])
    text = ''

    result1 = http_client.post_url(requests_count_async, 'requests_count')
    result2 = http_client.post_url(requests_count_async, 'requests_count')
    upstreams[requests_count_async].update(Upstream(requests_count_async, {}, [get_server(request, 'normal')]))
    result3 = http_client.post_url(requests_count_async, 'requests_count')

    async def batch_requests() -> RequestResult:
        _, _, _response = await asyncio.gather(result1, result2, result3)
        return _response

    requests_task = asyncio.create_task(batch_requests())
    await asyncio.sleep(0.1)

    check_all_servers_occupied(request, requests_count_async)
    response = await requests_task
    check_all_requests_done(request, requests_count_async)
    return response.data


@router.post('/requests_count')
async def post_page(request: Request) -> str:
    await asyncio.sleep(0.2)
    upstreams = request.app.service_discovery.get_upstreams_unsafe()
    servers = upstreams['requests_count_async'].servers
    return str(servers[0].stat_requests)
