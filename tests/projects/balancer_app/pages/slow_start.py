import time

from http_client.balancing import Upstream, Server

from frontik import media_types
from frontik.handler import PageHandler
from frontik.futures import AsyncGroup

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


class Page(PageHandler):
    def get_page(self):
        server = get_server(self, 'normal')
        server.weight = 5

        same_server = get_server(self, 'normal')
        same_server.weight = 5

        server_slow_start = Server('127.0.0.1:12345', weight=5, dc='Test')

        self.application.upstream_manager.update_upstream(
            Upstream('slow_start', {'slow_start_interval_sec': '0.1'}, [server]))
        self.text = ''

        def check_requests_cb():
            check_all_requests_done(self, 'slow_start')

        async_group = AsyncGroup(check_requests_cb)

        def callback_post(text, response):
            self.text = text

        self.post_url('slow_start', self.request.path, callback=async_group.add(callback_post))
        time.sleep(0.2)
        self.application.upstream_manager.update_upstream(
            Upstream('slow_start', {'slow_start_interval_sec': '1'}, [same_server, server_slow_start]))
        self.post_url('slow_start', self.request.path, callback=async_group.add(callback_post))
        time.sleep(1)
        self.post_url('slow_start', self.request.path, callback=async_group.add(callback_post))
        self.post_url('slow_start', self.request.path, callback=async_group.add(callback_post))

        check_all_servers_occupied(self, 'slow_start')

    def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = str(self.application.upstream_manager.upstreams['slow_start'].servers[1].stat_requests)
