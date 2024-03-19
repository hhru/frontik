from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler, router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        upstreams = self.application.upstream_manager.get_upstreams()
        upstreams['retry_on_timeout_async'] = Upstream(
            'retry_on_timeout_async',
            {},
            [get_server(self, 'broken'), get_server(self, 'normal')],
        )

        result = await self.delete_url(
            'retry_on_timeout_async',
            self.request.path,
            connect_timeout=0.1,
            request_timeout=0.3,
            max_timeout_tries=2,
        )

        if result.failed or result.data is None:
            raise HTTPError(500)

        self.text = result.data

        check_all_requests_done(self, 'retry_on_timeout_async')

    @router.delete()
    async def delete_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
