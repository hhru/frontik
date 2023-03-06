import asyncio

from http_client.balancing import Upstream, Server, UpstreamConfig

from frontik import media_types
from frontik.handler import PageHandler

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(PageHandler):
    async def get_page(self):
        server = get_server(self, 'normal')
        server.weight = 5

        server_slow_start = Server('127.0.0.1:12345', weight=5, dc='Test')

        upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=0.1)}
        self.application.upstream_manager.update_upstream(
            Upstream('slow_start_async', upstream_config, [server]))
        self.text = ''

        async def make_request(delay=0):
            await asyncio.sleep(delay)
            result = await self.post_url('slow_start_async', self.request.path)
            self.text = result.data

        await self.post_url('slow_start_async', self.request.path)

        await asyncio.sleep(0.5)

        upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=1)}
        self.application.upstream_manager.update_upstream(
            Upstream('slow_start_async', upstream_config, [server, server_slow_start]))

        request2 = self.run_task(make_request())
        request3 = self.run_task(make_request())
        request4 = self.run_task(make_request(1))

        await asyncio.gather(request2, request3)
        await asyncio.wait_for(request4, timeout=1)

        check_all_requests_done(self, 'slow_start_async')

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        servers = self.application.upstream_manager.upstreams['slow_start_async'].servers
        if len(servers) > 1:
            self.text = str(servers[1].stat_requests)
