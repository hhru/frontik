from fastapi import Request
from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik.dependencies import HttpClient
from frontik.routing import router
from frontik.util import gather_list
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_servers_were_occupied


@router.get('/retry_connect_timeout')
async def get_page(request: Request, http_client: HttpClient) -> str:
    retry_connect_timeout = 'retry_connect_timeout'
    upstreams = request.app.service_discovery._upstreams
    upstreams[retry_connect_timeout] = Upstream(
        retry_connect_timeout,
        {},
        [get_server(request, 'free'), get_server(request, 'normal')],
    )
    text = ''

    requests = [
        http_client.post_url(retry_connect_timeout, retry_connect_timeout),
        http_client.post_url(retry_connect_timeout, retry_connect_timeout),
        http_client.post_url(retry_connect_timeout, retry_connect_timeout),
    ]
    results = await gather_list(*requests)

    check_all_servers_were_occupied(request, retry_connect_timeout)

    for result in results:
        if result.error or result.data is None:
            raise HTTPError(500)

        text += result.data

    return text


@router.post('/retry_connect_timeout')
async def post_page() -> str:
    return 'result'
