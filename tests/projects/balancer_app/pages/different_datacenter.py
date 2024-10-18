from http_client.balancing import Upstream
from http_client.request_response import NoAvailableServerException
from tornado.web import HTTPError

from fastapi import Request
from frontik import media_types
from frontik.dependencies import HttpClientT
from frontik.routing import router
from tests.projects.balancer_app import get_server


@router.get('/different_datacenter')
async def get_page(request: Request, http_client: HttpClientT):
    free_server = get_server(request, 'free')
    free_server.datacenter = 'dc1'
    normal_server = get_server(request, 'normal')
    normal_server.datacenter = 'dc2'

    upstream = Upstream('different_datacenter', {}, [free_server, normal_server])
    request.app.service_discovery.get_upstreams_unsafe()['different_datacenter'] = upstream

    u = request.url
    result = await http_client.post_url('different_datacenter', u.path + '?' + u.query)
    for server in upstream.servers:
        if server.stat_requests != 0:
            raise HTTPError(500)

    if result.exc is not None and isinstance(result.exc, NoAvailableServerException):
        return 'no backend available'

    return result.data


@router.post('/different_datacenter')
async def post_page():
    return 'result'
