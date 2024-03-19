import asyncio

from http_client.balancing import Server, Upstream, UpstreamConfig

from frontik import media_types
from frontik.handler import PageHandler, router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_were_occupied


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        server = get_server(self, 'normal')
        server.weight = 5

        same_server = get_server(self, 'normal')
        same_server.weight = 5

        server_slow_start = Server('127.0.0.1:12345', weight=5, dc='Test')

        upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=0.1)}
        upstreams = self.application.upstream_manager.get_upstreams()
        upstreams['slow_start'] = Upstream('slow_start', upstream_config, [server])
        self.text = ''

        await self.post_url('slow_start', self.request.path)

        await asyncio.sleep(0.2)
        upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=1)}
        upstreams['slow_start'].update(Upstream('slow_start', upstream_config, [same_server, server_slow_start]))

        await self.post_url('slow_start', self.request.path)

        await asyncio.sleep(1)

        requests = [self.post_url('slow_start', self.request.path), self.post_url('slow_start', self.request.path)]
        await asyncio.gather(*requests)

        check_all_servers_were_occupied(self, 'slow_start')

        self.text = str(server.stat_requests + server_slow_start.stat_requests)
        check_all_requests_done(self, 'slow_start')

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        upstreams = self.application.upstream_manager.get_upstreams()
        self.text = str(upstreams['slow_start'].servers[0].stat_requests)
