from http_client.balancing import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler
from frontik.util import gather_list
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_servers_were_occupied


class Page(PageHandler):
    async def get_page(self):
        self.application.upstream_manager.update_upstream(
            Upstream('retry_error', {}, [get_server(self, 'broken'), get_server(self, 'normal')]),
        )
        self.text = ''

        requests = [
            self.put_url('retry_error', self.request.path),
            self.put_url('retry_error', self.request.path),
            self.put_url('retry_error', self.request.path),
        ]
        results = await gather_list(*requests)

        check_all_servers_were_occupied(self, 'retry_error')

        for result in results:
            if result.error or result.data is None:
                raise HTTPError(500)

            self.text = self.text + result.data

    async def put_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
