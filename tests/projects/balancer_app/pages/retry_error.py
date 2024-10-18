from http_client.balancing import Upstream
from tornado.web import HTTPError

from fastapi import Request
from frontik.dependencies import HttpClientT
from frontik.routing import router
from frontik.util import gather_list
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_servers_were_occupied


@router.get('/retry_error')
async def get_page(request: Request, http_client: HttpClientT):
    upstreams = request.app.service_discovery.get_upstreams_unsafe()
    retry_error = 'retry_error'
    upstreams[retry_error] = Upstream(
        retry_error, {}, [get_server(request, 'broken'), get_server(request, 'normal')]
    )

    text = ''

    requests = [
        http_client.put_url(retry_error, retry_error),
        http_client.put_url(retry_error, retry_error),
        http_client.put_url(retry_error, retry_error),
    ]
    results = await gather_list(*requests)

    check_all_servers_were_occupied(request, retry_error)

    for result in results:
        if result.error or result.data is None:
            raise HTTPError(500)

        text = text + result.data

    return text


@router.put('/retry_error')
async def put_page():
    return 'result'
