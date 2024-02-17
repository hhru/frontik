from asyncio import TimeoutError

from http_client.balancing import Upstream, UpstreamConfig

from frontik import handler, media_types
from frontik.handler import router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(handler.PageHandler):
    @router.get()
    async def get_page(self):
        self.application.upstream_manager.upstreams['no_retry_timeout_async'] = Upstream(
            'no_retry_timeout_async',
            {},
            [],
        )
        upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(max_timeout_tries=2)}
        self.application.upstream_manager.update_upstream(
            Upstream(
                'no_retry_timeout_async',
                upstream_config,
                [get_server(self, 'broken'), get_server(self, 'normal')],
            ),
        )

        result = await self.post_url('no_retry_timeout_async', self.request.path, request_timeout=0.2)

        if result.failed and isinstance(result.exc, TimeoutError):
            self.text = 'no retry timeout'
            return

        self.text = result.data

        check_all_requests_done(self, 'no_retry_timeout_async')

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
