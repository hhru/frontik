import asyncio

from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


class Page(PageHandler):
    async def get_page(self):
        self.application.upstream_manager.update_upstream(Upstream('retry_connect_timeout', {},
                                                                   [get_server(self, 'normal')]))
        self.text = ''

        async def make_request():
            result = await self.post_url('retry_connect_timeout', self.request.path)

            if result.failed or result.data is None:
                raise HTTPError(500)

            self.text = self.text + result.data

        request1 = self.run_task(make_request())
        request2 = self.run_task(make_request())
        request3 = self.run_task(make_request())

        await asyncio.sleep(0)

        check_all_servers_occupied(self, 'retry_connect_timeout')

        await asyncio.gather(request1, request2, request3)

        check_all_requests_done(self, 'retry_connect_timeout')

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
