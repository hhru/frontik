from fastapi import Request
from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik.dependencies import http_client
from frontik.routing import router
from frontik.util import gather_list
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_servers_were_occupied


@router.get('/retry_connect')
async def get_page(request: Request) -> str:
    upstreams = request.app.service_discovery.get_upstreams_unsafe()
    retry_connect = 'retry_connect'
    upstreams[retry_connect] = Upstream(
        retry_connect,
        {},
        [get_server(request, 'free'), get_server(request, 'normal')],
    )
    text = ''

    requests = [
        http_client.post_url(retry_connect, retry_connect),
        http_client.post_url(retry_connect, retry_connect),
        http_client.post_url(retry_connect, retry_connect),
    ]
    results = await gather_list(*requests)

    check_all_servers_were_occupied(request, retry_connect)

    for result in results:
        if result.failed or result.data is None:
            raise HTTPError(500)

        text = text + result.data

    return text


@router.post('/retry_connect')
async def post_page() -> str:
    return 'result'
