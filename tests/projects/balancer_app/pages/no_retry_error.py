from fastapi import Request
from http_client.balancing import Upstream

from frontik.dependencies import HttpClient
from frontik.routing import router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


@router.get('/no_retry_error')
async def get_page(request: Request, http_client: HttpClient) -> str:
    upstreams = request.app.service_discovery._upstreams
    no_retry_error = 'no_retry_error'
    upstreams[no_retry_error] = Upstream(
        no_retry_error,
        {},
        [get_server(request, 'broken'), get_server(request, 'normal')],
    )

    result = await http_client.post_url(no_retry_error, no_retry_error)
    if result.error and result.status_code == 500:
        text = 'no retry error'
    else:
        text = result.data

    check_all_requests_done(request, no_retry_error)

    return text


@router.post('/no_retry_error')
async def post_page():
    return 'result'
