from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler, router
from frontik.util import gather_list
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_servers_were_occupied


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        upstreams = self.application.upstream_manager.get_upstreams()
        upstreams['retry_connect'] = Upstream(
            'retry_connect',
            {},
            [get_server(self, 'free'), get_server(self, 'normal')],
        )
        self.text = ''

        requests = [
            self.post_url('retry_connect', self.request.path),
            self.post_url('retry_connect', self.request.path),
            self.post_url('retry_connect', self.request.path),
        ]
        results = await gather_list(*requests)

        check_all_servers_were_occupied(self, 'retry_connect')

        for result in results:
            if result.failed or result.data is None:
                raise HTTPError(500)

            self.text = self.text + result.data

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
