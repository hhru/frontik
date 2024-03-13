import asyncio

from http_client.balancing import Upstream

from frontik import media_types
from frontik.handler import PageHandler, router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_were_occupied


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        upstreams = self.application.upstream_manager.get_upstreams()
        upstreams['requests_count'] = Upstream('requests_count', {}, [get_server(self, 'normal')])
        self.text = ''

        async def make_request() -> None:
            await self.post_url('requests_count', self.request.path)

        async def request_with_processing() -> None:
            result = await self.post_url('requests_count', self.request.path)
            self.text = result.data
            check_all_requests_done(self, 'requests_count')

        self.run_task(make_request())
        self.run_task(make_request())
        upstreams['requests_count'] = Upstream('requests_count', {}, [get_server(self, 'normal')])
        self.run_task(request_with_processing())
        await asyncio.sleep(0.1)
        check_all_servers_were_occupied(self, 'requests_count')

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        upstreams = self.application.upstream_manager.get_upstreams()
        self.text = str(upstreams['requests_count'].servers[0].stat_requests)
