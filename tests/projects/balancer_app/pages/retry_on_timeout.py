from fastapi import Request
from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik.dependencies import HttpClientT
from frontik.routing import router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


@router.get('/retry_on_timeout')
async def get_page(request: Request, http_client: HttpClientT) -> str:
    upstreams = request.app.service_discovery.get_upstreams_unsafe()
    retry_on_timeout = 'retry_on_timeout'
    upstreams[retry_on_timeout] = Upstream(
        retry_on_timeout,
        {},
        [get_server(request, 'broken'), get_server(request, 'normal')],
    )

    result = await http_client.delete_url(
        retry_on_timeout,
        retry_on_timeout,
        connect_timeout=0.1,
        request_timeout=0.3,
        max_timeout_tries=2,
    )

    if result.error or result.data is None:
        raise HTTPError(500)

    check_all_requests_done(request, retry_on_timeout)

    return result.data


@router.delete('/retry_on_timeout')
async def delete_page() -> str:
    return 'result'
