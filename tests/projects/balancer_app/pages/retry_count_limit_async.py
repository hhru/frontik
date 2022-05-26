from http_client import Upstream

from frontik.handler import AwaitablePageHandler

from tests.projects.balancer_app import get_server


class Page(AwaitablePageHandler):
    async def get_page(self):
        upstream = Upstream(
            'retry_count_limit_async',
            {'max_tries': 3},
            [get_server(self, 'free'), get_server(self, 'free'), get_server(self, 'free'), get_server(self, 'free')])

        self.application.http_client_factory.update_upstream(upstream)

        self.text = ''

        await self.get_url('retry_count_limit_async', self.request.path)

        self.text = str(sum(server.requests for server in upstream.servers))
