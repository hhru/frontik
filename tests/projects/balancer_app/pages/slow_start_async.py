import asyncio

from http_client import Upstream, Server

from frontik import media_types
from frontik.handler import AwaitablePageHandler

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(AwaitablePageHandler):
    async def get_page(self):
        server = get_server(self, 'normal')
        server.weight = 5

        server_slow_start = Server('127.0.0.1:12345', weight=5, dc='Test')

        self.application.http_client_factory.update_upstream(
            Upstream('slow_start_async', {'slow_start_interval_sec': '0.1'}, [server]))
        self.text = ''

        async def make_request():
            result = await self.post_url('slow_start_async', self.request.path)
            self.text = result.data

        await self.post_url('slow_start_async', self.request.path)

        await asyncio.sleep(0.5)

        self.application.http_client_factory.update_upstream(
            Upstream('slow_start_async', {'slow_start_interval_sec': '10'}, [server, server_slow_start]))

        request2 = self.run_task(make_request())
        request3 = self.run_task(make_request())

        await asyncio.gather(request2, request3)

        check_all_requests_done(self, 'slow_start_async')

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        servers = self.application.http_client_factory.upstreams['slow_start_async'].servers
        if len(servers) > 1:
            self.text = str(servers[1].requests)
