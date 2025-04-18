from fastapi import Request
from http_client.balancing import Upstream, UpstreamConfig

from frontik.dependencies import HttpClient
from frontik.routing import router
from tests import find_free_port
from tests.projects.balancer_app import get_server_with_port


@router.get('/retry_count_limit')
async def get_page(request: Request, http_client: HttpClient) -> str:
    retry_count_limit = 'retry_count_limit'
    upstream = Upstream(
        retry_count_limit,
        {Upstream.DEFAULT_PROFILE: UpstreamConfig(max_tries=3)},
        [
            get_server_with_port(find_free_port(11000, 20000)),
            get_server_with_port(find_free_port(12000, 20000)),
            get_server_with_port(find_free_port(13000, 20000)),
            get_server_with_port(find_free_port(14000, 20000)),
        ],
    )

    upstreams = request.app.service_discovery._upstreams
    upstreams[retry_count_limit] = upstream

    await http_client.get_url(retry_count_limit, retry_count_limit)

    return str(sum(server.stat_requests for server in upstream.servers))
