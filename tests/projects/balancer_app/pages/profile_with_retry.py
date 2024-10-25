from fastapi import Request
from http_client.balancing import Upstream, UpstreamConfig
from tornado.web import HTTPError

from frontik.dependencies import HttpClient
from frontik.routing import router
from tests.projects.balancer_app import get_server


@router.get('/profile_with_retry')
async def get_page(request: Request, http_client: HttpClient) -> str:
    servers = [get_server(request, 'broken'), get_server(request, 'normal')]
    profile_with_retry = 'profile_with_retry'
    upstream_config = {
        Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=0),
        'profile_without_retry': UpstreamConfig(max_tries=1),
        profile_with_retry: UpstreamConfig(max_tries=2),
    }
    upstreams = request.app.service_discovery.get_upstreams_unsafe()
    upstreams[profile_with_retry] = Upstream(
        profile_with_retry,
        upstream_config,
        servers,
    )

    result = await http_client.put_url(profile_with_retry, profile_with_retry, profile=profile_with_retry)

    if result.failed or result.data is None:
        raise HTTPError(500)

    return result.data


@router.put('/profile_with_retry')
async def put_page() -> str:
    return 'result'
