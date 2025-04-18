from fastapi import Request
from http_client.balancing import Upstream

from frontik.dependencies import HttpClient
from frontik.routing import router
from tests.projects.balancer_app import get_server


@router.get('/speculative_no_retry')
async def get_page(request: Request, http_client: HttpClient) -> str:
    upstreams = request.app.service_discovery._upstreams
    speculative_no_retry = 'speculative_no_retry'
    upstreams[speculative_no_retry] = Upstream(
        speculative_no_retry,
        {},
        [get_server(request, 'broken'), get_server(request, 'normal')],
    )

    result = await http_client.post_url(
        speculative_no_retry,
        speculative_no_retry,
        connect_timeout=0.1,
        request_timeout=0.5,
        max_timeout_tries=1,
        speculative_timeout_pct=0.10,
    )

    if result.failed or result.status_code == 500:
        return 'no retry'

    return result.data


@router.post('/speculative_no_retry')
async def post_page() -> str:
    return 'result'
