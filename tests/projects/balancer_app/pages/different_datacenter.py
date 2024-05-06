from fastapi import HTTPException
from http_client.balancing import Upstream
from http_client.request_response import NoAvailableServerException

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router
from tests.projects.balancer_app import get_server


@router.get('/different_datacenter', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    free_server = get_server(handler, 'free')
    free_server.datacenter = 'dc1'
    normal_server = get_server(handler, 'normal')
    normal_server.datacenter = 'dc2'

    upstream = Upstream('different_datacenter', {}, [free_server, normal_server])
    handler.application.upstream_manager.get_upstreams()['different_datacenter'] = upstream

    result = await handler.post_url('different_datacenter', handler.path)
    for server in upstream.servers:
        if server.stat_requests != 0:
            raise HTTPException(500)

    if result.exc is not None and isinstance(result.exc, NoAvailableServerException):
        handler.text = 'no backend available'
        return

    handler.text = result.data


@router.post('/different_datacenter', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'
