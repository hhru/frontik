from http_client.balancing import Upstream, UpstreamConfig
from tornado.web import HTTPError

from frontik import media_types
from frontik.handler import PageHandler, router
from frontik.util import gather_list
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        upstream_config = {Upstream.DEFAULT_PROFILE: UpstreamConfig(retry_policy={503: {'idempotent': 'true'}})}
        upstreams = self.application.upstream_manager.get_upstreams()
        upstreams['retry_non_idempotent_503'] = Upstream(
            'retry_non_idempotent_503',
            upstream_config,
            [get_server(self, 'normal')],
        )
        upstreams['do_not_retry_non_idempotent_503'] = Upstream(
            'do_not_retry_non_idempotent_503',
            {},
            [get_server(self, 'broken')],
        )

        res1, res2 = await gather_list(
            self.post_url('retry_non_idempotent_503', self.request.path),
            self.post_url('do_not_retry_non_idempotent_503', self.request.path),
        )

        if res1.error or res1.data is None:
            raise HTTPError(500)
        self.text = res1.data

        if res2.status_code != 503:
            raise HTTPError(500)

        check_all_requests_done(self, 'retry_non_idempotent_503')
        check_all_requests_done(self, 'do_not_retry_non_idempotent_503')

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
