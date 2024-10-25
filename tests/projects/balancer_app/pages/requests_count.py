import asyncio

from fastapi import Request
from http_client.balancing import Upstream

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

    await asyncio.sleep(0)

    check_all_servers_occupied(request, requests_count_async)

    _, _, response = await asyncio.gather(result1, result2, result3)

    check_all_requests_done(request, requests_count_async)

    return response.data


@router.post('/requests_count')
async def post_page(request: Request) -> str:
    upstreams = request.app.service_discovery.get_upstreams_unsafe()
    servers = upstreams['requests_count_async'].servers
    return str(servers[0].stat_requests)
