from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler, router
from tests.projects.balancer_app import get_server


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        upstreams = self.application.upstream_manager.get_upstreams()
        upstreams['speculative_retry'] = Upstream(
            'speculative_retry',
            {},
            [get_server(self, 'broken'), get_server(self, 'normal')],
        )

        result = await self.put_url(
            'speculative_retry',
            self.request.path,
            connect_timeout=0.1,
            request_timeout=0.5,
            max_timeout_tries=1,
            speculative_timeout_pct=0.1,
        )

        if result.failed or result.data is None:
            raise HTTPError(500)

        self.text = result.data

    @router.put()
    async def put_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
