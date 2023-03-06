import asyncio
import time

from http_client.balancing import Upstream, Server, UpstreamConfig

from frontik import media_types
from frontik.handler import PageHandler

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


class Page(PageHandler):
    async def get_page(self):
        server = get_server(self, 'normal')
        server.weight = 5

        same_server = get_server(self, 'normal')
        same_server.weight = 5

        server_slow_start = Server('127.0.0.1:12345', weight=5, dc='Test')

        upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=0.1)}
        self.application.upstream_manager.update_upstream(
            Upstream('slow_start', upstream_config, [server]))
        self.text = ''

        requests = []

        requests.append(self.post_url('slow_start', self.request.path))
        time.sleep(0.2)
        upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=1)}
        self.application.upstream_manager.update_upstream(
            Upstream('slow_start', upstream_config, [same_server, server_slow_start]))
        requests.append(self.post_url('slow_start', self.request.path))
        time.sleep(1)
        requests.append(self.post_url('slow_start', self.request.path))
        requests.append(self.post_url('slow_start', self.request.path))

        check_all_servers_occupied(self, 'slow_start')

        res = await asyncio.gather(*requests)
        self.text = res[-1].data
        check_all_requests_done(self, 'slow_start')

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = str(self.application.upstream_manager.upstreams['slow_start'].servers[1].stat_requests)
