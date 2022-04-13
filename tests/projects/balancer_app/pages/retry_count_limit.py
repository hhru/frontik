from http_client import Upstream

from frontik.handler import PageHandler

from tests.projects.balancer_app import get_server


class Page(PageHandler):
    def get_page(self):
        upstream = Upstream(
            'retry_count_limit',
            {'max_tries': 3},
            [get_server(self, 'free'), get_server(self, 'free'), get_server(self, 'free'), get_server(self, 'free')])

        self.application.http_client_factory.update_upstream(upstream)

        self.text = ''

        yield self.get_url('retry_count_limit', self.request.path)

        self.text = str(sum(server.requests for server in upstream.servers))
