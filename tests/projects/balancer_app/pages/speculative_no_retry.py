from http_client import Upstream

from frontik import media_types
from frontik.handler import AwaitablePageHandler
from tests.projects.balancer_app import get_server


class Page(AwaitablePageHandler):
    async def get_page(self):
        self.application.http_client_factory.upstreams['speculative_no_retry'] = Upstream('speculative_no_retry',
                                                                                          {}, [])
        self.application.http_client_factory.update_upstream(
            Upstream('speculative_no_retry', {}, [get_server(self, 'broken'), get_server(self, 'normal')]))

        result = await self.post_url('speculative_no_retry', self.request.path, connect_timeout=0.1,
                                     request_timeout=0.5, max_timeout_tries=1, speculative_timeout=0.10)

        if result.failed or result.response.code == 500:
            self.text = 'no retry'
            return

        self.text = result.data

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
