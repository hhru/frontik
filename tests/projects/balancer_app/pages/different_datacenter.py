from fastapi import Request
from http_client.balancing import Upstream
from http_client.request_response import NoAvailableServerException
from tornado.web import HTTPError

from frontik.dependencies import HttpClient
from frontik.routing import router
from tests.projects.balancer_app import get_server


@router.get('/different_datacenter')
async def get_page(request: Request, http_client: HttpClient) -> str:
    free_server = get_server(request, 'free')
    free_server.datacenter = 'dc1'
    normal_server = get_server(request, 'normal')
    normal_server.datacenter = 'dc2'

    different_datacenter = 'different_datacenter'
    upstream = Upstream(different_datacenter, {}, [free_server, normal_server])
    request.app.service_discovery._upstreams[different_datacenter] = upstream

    result = await http_client.post_url(different_datacenter, different_datacenter)
    for server in upstream.servers:
        if server.stat_requests != 0:
            raise HTTPError(500)

    if result.exc is not None and isinstance(result.exc, NoAvailableServerException):
        return 'no backend available'

    return result.data


@router.post('/different_datacenter')
async def post_page():
    return 'result'
