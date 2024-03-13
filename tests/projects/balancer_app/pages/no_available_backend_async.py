from http_client.balancing import Upstream
from http_client.request_response import NoAvailableServerException

from frontik import handler, media_types
from frontik.handler import router
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(handler.PageHandler):
    @router.get()
    async def get_page(self):
        upstreams = self.application.upstream_manager.get_upstreams()
        upstreams['no_available_backend'] = Upstream('no_available_backend', {}, [])

        request = self.post_url('no_available_backend', self.request.path)
        check_all_requests_done(self, 'no_available_backend')

        result = await request

        if result.exc is not None and isinstance(result.exc, NoAvailableServerException):
            self.text = 'no backend available'
            return

        self.text = result.text

        check_all_requests_done(self, 'no_available_backend')

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
