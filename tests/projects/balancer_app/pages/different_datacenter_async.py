from http_client import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import AwaitablePageHandler

from tests.projects.balancer_app import get_server


class Page(AwaitablePageHandler):
    async def get_page(self):
        free_server = get_server(self, 'free')
        free_server.rack = 'rack1'
        free_server.datacenter = 'Test'
        normal_server = get_server(self, 'normal')
        normal_server.rack = 'rack1'
        normal_server.datacenter = 'dc2'

        self.application.http_client_factory.update_upstream(
            Upstream('different_datacenter', {}, [free_server, normal_server]))

        result = await self.post_url('different_datacenter', self.request.path)

        server = next(
            s for s in self._http_client.upstreams.get('different_datacenter').servers if
            self.get_argument('free') in s.address)

        if server.requests != 1:
            raise HTTPError(500)

        if result.failed and result.response.code == 502:
            self.text = 'no backend available'
            return

        self.text = result.data

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
