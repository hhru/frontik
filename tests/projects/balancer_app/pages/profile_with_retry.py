from fastapi import HTTPException
from http_client.balancing import Upstream, UpstreamConfig

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router
from tests.projects.balancer_app import get_server


@router.get('/profile_with_retry', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    servers = [get_server(handler, 'broken'), get_server(handler, 'normal')]
    upstream_config = {
        Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=0),
        'profile_without_retry': UpstreamConfig(max_tries=1),
        'profile_with_retry': UpstreamConfig(max_tries=2),
    }
    upstreams = handler.application.upstream_manager.get_upstreams()
    upstreams['profile_with_retry'] = Upstream(
        'profile_with_retry',
        upstream_config,
        servers,
    )

    result = await handler.put_url('profile_with_retry', handler.path, profile='profile_with_retry')

    if result.failed or result.data is None:
        raise HTTPException(500)

    handler.text = result.data


@router.put('/profile_with_retry', cls=PageHandler)
async def put_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'
