from http_client.balancing import Upstream
from tornado.web import HTTPError

from fastapi import Request
from frontik.dependencies import HttpClientT
from frontik.routing import router
from frontik.util import gather_list
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_servers_were_occupied


@router.get('/retry_connect')
async def get_page(request: Request, http_client: HttpClientT):
    upstreams = request.app.service_discovery.get_upstreams_unsafe()
    upstreams['retry_connect'] = Upstream(
        'retry_connect',
        {},
        [get_server(request, 'free'), get_server(request, 'normal')],
    )
    text = ''

    u = request.url
    requests = [
        http_client.post_url('retry_connect', u.path + '?' + u.query),
        http_client.post_url('retry_connect', u.path + '?' + u.query),
        http_client.post_url('retry_connect', u.path + '?' + u.query),
    ]
    results = await gather_list(*requests)

    check_all_servers_were_occupied(request, 'retry_connect')

    for result in results:
        if result.failed or result.data is None:
            raise HTTPError(500)

        text = text + result.data

    return text


@router.post('/retry_connect')
async def post_page():
    return 'result'
