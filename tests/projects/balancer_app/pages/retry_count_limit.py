from http_client.balancing import Upstream, UpstreamConfig

from frontik.handler import PageHandler, router
from tests.instances import find_free_port
from tests.projects.balancer_app import get_server_with_port


class Page(PageHandler):
    @router.get()
    async def get_page(self):
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

        upstreams = self.application.upstream_manager.get_upstreams()
        upstreams['retry_count_limit'] = upstream

        self.text = ''

        await self.get_url('retry_count_limit', self.request.path)

        self.text = str(sum(server.stat_requests for server in upstream.servers))
