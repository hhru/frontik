from http_client.balancing import Upstream, UpstreamConfig
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler
from tests.projects.balancer_app import get_server


class Page(PageHandler):
    def get_page(self):
        servers = [get_server(self, 'broken'), get_server(self, 'normal')]
        upstream_config = {
            Upstream.DEFAULT_PROFILE: UpstreamConfig(slow_start_interval=0),
            "profile_without_retry": UpstreamConfig(max_tries=1),
            "profile_with_retry": UpstreamConfig(max_tries=2)
        }
        self.application.upstream_manager.upstreams['profile_with_retry'] = Upstream('profile_with_retry',
                                                                                     upstream_config, servers)

        result = yield self.put_url('profile_with_retry', self.request.path, profile="profile_with_retry")

        if result.failed or result.data is None:
            raise HTTPError(500)

        self.text = result.data

    def put_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
