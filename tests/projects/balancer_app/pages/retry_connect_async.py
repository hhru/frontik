import asyncio

from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler, router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_servers_were_occupied


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        upstreams = self.application.upstream_manager.get_upstreams()
        upstreams['retry_connect_async'] = Upstream(
            'retry_connect_async',
            {},
            [get_server(self, 'free'), get_server(self, 'normal')],
        )
        self.text = ''

        async def make_request() -> None:
            result = await self.post_url('retry_connect_async', self.request.path)

            if result.failed or result.data is None:
                raise HTTPError(500)

            self.text = self.text + result.data

        request1 = self.run_task(make_request())
        request2 = self.run_task(make_request())
        request3 = self.run_task(make_request())

        await asyncio.sleep(0.1)

        check_all_servers_were_occupied(self, 'retry_connect_async')

        await asyncio.gather(request1, request2, request3)

        check_all_servers_were_occupied(self, 'retry_connect_async')

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
