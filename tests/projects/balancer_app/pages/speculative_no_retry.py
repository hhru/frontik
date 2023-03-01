from http_client.balancing import Upstream

from frontik import media_types
from frontik.handler import PageHandler
from tests.projects.balancer_app import get_server


class Page(PageHandler):
    async def get_page(self):
        self.application.upstream_manager.upstreams['speculative_no_retry'] = Upstream('speculative_no_retry',
                                                                                       {}, [])
        self.application.upstream_manager.update_upstream(
            Upstream('speculative_no_retry', {}, [get_server(self, 'broken'), get_server(self, 'normal')]))

        result = await self.post_url('speculative_no_retry', self.request.path, connect_timeout=0.1,
                                     request_timeout=0.5, max_timeout_tries=1, speculative_timeout_pct=0.10)

        if result.failed or result.response.code == 500:
            self.text = 'no retry'
            return

        self.text = result.data

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
