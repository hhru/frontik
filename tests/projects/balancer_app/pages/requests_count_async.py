import asyncio

from http_client.balancing import Upstream

from frontik import media_types
from frontik.handler import PageHandler, router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        upstreams = self.application.upstream_manager.get_upstreams()
        upstreams['requests_count_async'] = Upstream('requests_count_async', {}, [get_server(self, 'normal')])
        self.text = ''

        result1 = self.post_url('requests_count_async', self.request.path)
        result2 = self.post_url('requests_count_async', self.request.path)
        upstreams['requests_count_async'].update(Upstream('requests_count_async', {}, [get_server(self, 'normal')]))
        result3 = self.post_url('requests_count_async', self.request.path)

        await asyncio.sleep(0)

        check_all_servers_occupied(self, 'requests_count_async')

        _, _, response = await asyncio.gather(result1, result2, result3)

        self.text = response.data

        check_all_requests_done(self, 'requests_count_async')

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        upstreams = self.application.upstream_manager.get_upstreams()
        servers = upstreams['requests_count_async'].servers
        self.text = str(servers[0].stat_requests)
