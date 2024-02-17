from http_client.balancing import Upstream
from http_client.request_response import NoAvailableServerException

from frontik import handler, media_types
from frontik.handler import router
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(handler.PageHandler):
    @router.get()
    async def get_page(self):
        self.application.upstream_manager.update_upstream(Upstream('no_available_backend', {}, []))

        async def request_with_processing() -> None:
            result = await self.post_url('no_available_backend', self.request.path)
            if result.exc is not None and isinstance(result.exc, NoAvailableServerException):
                self.text = 'no backend available'
            else:
                self.text = result.data
            check_all_requests_done(self, 'no_available_backend')

        self.run_task(request_with_processing())
        check_all_requests_done(self, 'no_available_backend')

    @router.post()
    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
