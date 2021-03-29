from http_client import Upstream

from frontik import handler, media_types
from frontik.futures import AsyncGroup

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(handler.PageHandler):
    def get_page(self):
        self.application.upstream_caches.upstreams['no_retry_timeout'] = Upstream('no_retry_timeout', {},
                                                                                  [get_server(self, 'broken'),
                                                                                   get_server(self, 'normal')])

        def check_requests_cb():
            check_all_requests_done(self, 'no_retry_timeout')

        async_group = AsyncGroup(check_requests_cb)

        def callback_post(text, response):
            if response.error and response.code == 599:
                self.text = 'no retry timeout'
                return

            self.text = text

        self.post_url('no_retry_timeout', self.request.path, callback=async_group.add(callback_post),
                      request_timeout=0.2)

    def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
