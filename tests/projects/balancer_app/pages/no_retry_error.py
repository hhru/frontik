from http_client.balancing import Upstream

from frontik import handler, media_types
from frontik.handler import router
from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(handler.PageHandler):
    @router.get()
    async def get_page(self):
        upstreams = self.application.upstream_manager.get_upstreams()
        upstreams['no_retry_error'] = Upstream('no_retry_error', {}, [get_server(self, 'broken')])

        result = await self.post_url('no_retry_error', self.request.path)
        if result.error and result.status_code == 500:
            self.text = 'no retry error'
        else:
            self.text = result.data

        check_all_requests_done(self, 'no_retry_error')

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
