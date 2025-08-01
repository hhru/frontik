import asyncio

from fastapi import Request
from http_client.balancing import Upstream, UpstreamConfig, UpstreamConfigs

from frontik.dependencies import HttpClient
from frontik.routing import router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_were_occupied


@router.get('/slow_start')
async def get_page(request: Request, http_client: HttpClient) -> str:
    server = get_server(request, 'normal')
    server.weight = 5

    same_server = get_server(request, 'normal')
    same_server.weight = 5

    server_slow_start = get_server(request, 'free')
    server_slow_start.weight = 5

    upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=0.1)}
    upstreams = request.app.service_discovery._upstreams
    slow_start = 'slow_start'
    upstreams[slow_start] = Upstream(slow_start, UpstreamConfigs(upstream_config), [server])

    await http_client.post_url(slow_start, slow_start)

    await asyncio.sleep(0.2)
    upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=1)}
    upstreams[slow_start].update(
        Upstream(slow_start, UpstreamConfigs(upstream_config), [same_server, server_slow_start])
    )

    await http_client.post_url(slow_start, slow_start)

    await asyncio.sleep(1)

    requests = [http_client.post_url(slow_start, slow_start), http_client.post_url(slow_start, slow_start)]
    await asyncio.gather(*requests)

    check_all_servers_were_occupied(request, slow_start)

    check_all_requests_done(request, slow_start)
    return str(server.stat_requests + server_slow_start.stat_requests)


@router.post('/slow_start')
async def post_page(request: Request) -> str:
    upstream = request.app.service_discovery.get_upstream('slow_start')
    return str(upstream.servers[0].stat_requests)
