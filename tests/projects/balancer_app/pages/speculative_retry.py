from fastapi import Request
from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik.dependencies import http_client
from frontik.routing import router
from tests.projects.balancer_app import get_server


@router.get('/speculative_retry')
async def get_page(request: Request) -> str:
    upstreams = request.app.service_discovery.get_upstreams_unsafe()
    speculative_retry = 'speculative_retry'
    upstreams[speculative_retry] = Upstream(
        speculative_retry,
        {},
        [get_server(request, 'broken'), get_server(request, 'normal')],
    )

    result = await http_client.put_url(
        speculative_retry,
        speculative_retry,
        connect_timeout=0.1,
        request_timeout=0.5,
        max_timeout_tries=1,
        speculative_timeout_pct=0.1,
    )

    if result.failed or result.data is None:
        raise HTTPError(500)

    return result.data


@router.put('/speculative_retry')
async def put_page() -> str:
    return 'result'
