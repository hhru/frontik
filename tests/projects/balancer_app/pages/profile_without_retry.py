from http_client.balancing import Upstream, UpstreamConfig

from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router
from tests.projects.balancer_app import get_server


@plain_router.get('/profile_without_retry', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    servers = [get_server(handler, 'broken'), get_server(handler, 'normal')]
    upstream_config = {
        Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=0),
        'profile_without_retry': UpstreamConfig(max_tries=1),
        'profile_with_retry': UpstreamConfig(max_tries=2),
    }
    upstreams = handler.application.service_discovery.get_upstreams_unsafe()
    upstreams['profile_without_retry'] = Upstream(
        'profile_without_retry',
        upstream_config,
        servers,
    )
    result = await handler.put_url('profile_without_retry', handler.path, profile='profile_without_retry')

    if result.failed or result.status_code == 500:
        handler.text = 'no retry'
        return

    handler.text = result.data


@plain_router.put('/profile_without_retry', cls=PageHandler)
async def put_page(handler=get_current_handler()):
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
    handler.text = 'result'
