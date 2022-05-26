import asyncio

from http_client import Upstream
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import AwaitablePageHandler

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(AwaitablePageHandler):
    async def get_page(self):
        idempotent_retry_policy = {
            'retry_policy': {
                503: {
                    "idempotent": "true"
                }
            }
        }
        self.application.http_client_factory.update_upstream(Upstream('retry_non_idempotent_503_async',
                                                                      idempotent_retry_policy,
                                                                      [get_server(self, 'normal')]))

        self.application.http_client_factory.update_upstream(Upstream('do_not_retry_non_idempotent_503_async',
                                                                      {},
                                                                      [get_server(self, 'broken')]))

        async def post_with_retry():
            result = await self.post_url('retry_non_idempotent_503_async', self.request.path)

            if result.failed or result.data is None:
                raise HTTPError(500)

            self.text = result.data

        async def post_without_retry():
            result = await self.post_url('do_not_retry_non_idempotent_503_async', self.request.path)

            if result.response.code != 503:
                raise HTTPError(500)

        await asyncio.gather(
            self.run_task(post_with_retry()),
            self.run_task(post_without_retry()),
        )

        check_all_requests_done(self, 'retry_non_idempotent_503_async')
        check_all_requests_done(self, 'do_not_retry_non_idempotent_503_async')

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
