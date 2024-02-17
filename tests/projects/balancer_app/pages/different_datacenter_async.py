from http_client.balancing import Upstream
from http_client.request_response import NoAvailableServerException
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler, router
from tests.projects.balancer_app import get_server


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        free_server = get_server(self, 'free')
        free_server.datacenter = 'dc1'
        normal_server = get_server(self, 'normal')
        normal_server.datacenter = 'dc2'

        self.application.upstream_manager.update_upstream(
            Upstream('different_datacenter', {}, [free_server, normal_server]),
        )

        result = await self.post_url('different_datacenter', self.request.path)

        for server in self.application.upstream_manager.upstreams.get('different_datacenter').servers:
            if server.stat_requests != 0:
                raise HTTPError(500)

        if result.exc is not None and isinstance(result.exc, NoAvailableServerException):
            self.text = 'no backend available'
            return

        self.text = result.data

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
