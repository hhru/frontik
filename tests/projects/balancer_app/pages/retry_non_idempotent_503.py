from http_client import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler
from frontik.futures import AsyncGroup

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(PageHandler):
    def get_page(self):
        idempotent_retry_policy = {
            'retry_policy': {
                503: {
                    "idempotent": "true"
                }
            }
        }
        self.application.http_client_factory.update_upstream(
            Upstream('retry_non_idempotent_503', idempotent_retry_policy, [get_server(self, 'normal')]))
        self.application.http_client_factory.update_upstream(
            Upstream('do_not_retry_non_idempotent_503', {}, [get_server(self, 'broken')]))

        def check_requests_cb():
            check_all_requests_done(self, 'retry_non_idempotent_503')
            check_all_requests_done(self, 'do_not_retry_non_idempotent_503')

        async_group = AsyncGroup(check_requests_cb)

        def callback_post_without_retry(_, response):
            if response.code != 503:
                raise HTTPError(500)

        def callback_post_with_retry(text, response):
            if response.error or text is None:
                raise HTTPError(500)

            self.text = text

        self.post_url('retry_non_idempotent_503', self.request.path,
                      callback=async_group.add(callback_post_with_retry))
        self.post_url('do_not_retry_non_idempotent_503', self.request.path,
                      callback=async_group.add(callback_post_without_retry))

    def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
