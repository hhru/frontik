from asyncio import TimeoutError

from fastapi import Request
from http_client.balancing import Upstream

from frontik.dependencies import HttpClient
from frontik.routing import router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


@router.get('/no_retry_timeout')
async def get_page(request: Request, http_client: HttpClient) -> str:
    upstreams = request.app.service_discovery._upstreams
    no_retry_timeout = 'no_retry_timeout'
    upstreams[no_retry_timeout] = Upstream(
        no_retry_timeout,
        {},
        [get_server(request, 'broken'), get_server(request, 'normal')],
    )

    result = await http_client.post_url(no_retry_timeout, no_retry_timeout, request_timeout=0.2)
    if result.failed and isinstance(result.exc, TimeoutError):
        text = 'no retry timeout'
    else:
        text = result.data

    check_all_requests_done(request, no_retry_timeout)

    return text


@router.post('/no_retry_timeout')
async def post_page():
    return 'result'
