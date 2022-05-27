from http_client import Upstream

from frontik import handler, media_types

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(handler.AwaitablePageHandler):
    async def get_page(self):
        self.application.http_client_factory.update_upstream(
            Upstream('no_retry_timeout_async', {'max_timeout_tries': 2},
                     [get_server(self, 'broken'), get_server(self, 'normal')]))

        result = await self.post_url('no_retry_timeout_async', self.request.path, request_timeout=0.2)

        if result.failed and result.response.code == 599:
            self.text = 'no retry timeout'
            return

        self.text = result.data

        check_all_requests_done(self, 'no_retry_timeout_async')

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
