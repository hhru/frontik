from http_client import Upstream

from frontik import media_types
from frontik.handler import PageHandler
from frontik.futures import AsyncGroup

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


class Page(PageHandler):
    async def get_page(self):
        self.application.upstream_caches.upstreams['requests_count'] = Upstream('requests_count', {},
                                                                                [get_server(self, 'normal')])
        self.text = ''

        def check_requests_cb():
            check_all_requests_done(self, 'requests_count')

        async_group = AsyncGroup(check_requests_cb)

        def callback_post(text, response):
            self.text = text

        self.post_url('requests_count', self.request.path)
        self.post_url('requests_count', self.request.path)
        self.application.upstream_caches.upstreams['requests_count'] = Upstream('requests_count', {},
                                                                                [get_server(self, 'normal')])
        self.post_url('requests_count', self.request.path, callback=async_group.add(callback_post))
        check_all_servers_occupied(self, 'requests_count')

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = str(self.application.http_client_factory.upstreams['requests_count'].servers[0].current_requests)
