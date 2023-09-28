from http_client.balancing import Upstream

from frontik import media_types
from frontik.handler import PageHandler

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


class Page(PageHandler):
    async def get_page(self):
        self.application.upstream_manager.update_upstream(Upstream('requests_count', {}, [get_server(self, 'normal')]))
        self.text = ''

        async def request_with_processing() -> None:
            result = await self.post_url('requests_count', self.request.path)
            self.text = result.data
            check_all_requests_done(self, 'requests_count')

        self.run_task(self.post_url('requests_count', self.request.path))  # type: ignore
        self.run_task(self.post_url('requests_count', self.request.path))  # type: ignore
        self.application.upstream_manager.update_upstream(Upstream('requests_count', {}, [get_server(self, 'normal')]))
        self.run_task(request_with_processing())
        check_all_servers_occupied(self, 'requests_count')

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = str(self.application.upstream_manager.upstreams['requests_count'].servers[0].current_requests)
