from http_client.balancing import Upstream, UpstreamConfig

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router
from tests.instances import find_free_port
from tests.projects.balancer_app import get_server_with_port


@plain_router.get('/retry_count_limit', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    upstream = Upstream(
        'retry_count_limit',
        {Upstream.DEFAULT_PROFILE: UpstreamConfig(max_tries=3)},
        [
            get_server_with_port(find_free_port(11000, 20000)),
            get_server_with_port(find_free_port(12000, 20000)),
            get_server_with_port(find_free_port(13000, 20000)),
            get_server_with_port(find_free_port(14000, 20000)),
        ],
    )

    upstreams = handler.application.upstream_manager.get_upstreams()
    upstreams['retry_count_limit'] = upstream

    handler.text = ''

    await handler.get_url('retry_count_limit', handler.path)

    handler.text = str(sum(server.stat_requests for server in upstream.servers))
