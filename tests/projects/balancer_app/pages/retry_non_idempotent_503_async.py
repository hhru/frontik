import asyncio

from http_client.balancing import Upstream, UpstreamConfig
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler, router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(retry_policy={503: {'idempotent': 'true'}})}
        upstreams = self.application.upstream_manager.get_upstreams()
        upstreams['retry_non_idempotent_503_async'] = Upstream(
            'retry_non_idempotent_503_async',
            upstream_config,
            [get_server(self, 'normal')],
        )
        upstreams['do_not_retry_non_idempotent_503_async'] = Upstream(
            'do_not_retry_non_idempotent_503_async',
            {},
            [get_server(self, 'broken')],
        )

        async def post_with_retry() -> None:
            result = await self.post_url('retry_non_idempotent_503_async', self.request.path)

            if result.failed or result.data is None:
                raise HTTPError(500)

            self.text = result.data

        async def post_without_retry() -> None:
            result = await self.post_url('do_not_retry_non_idempotent_503_async', self.request.path)

            if result.status_code != 503:
                raise HTTPError(500)

        await asyncio.gather(self.run_task(post_with_retry()), self.run_task(post_without_retry()))

        check_all_requests_done(self, 'retry_non_idempotent_503_async')
        check_all_requests_done(self, 'do_not_retry_non_idempotent_503_async')

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
