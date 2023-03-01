from http_client.balancing import Upstream

from frontik import handler, media_types

from tests.projects.balancer_app.pages import check_all_requests_done


class Page(handler.PageHandler):
    async def get_page(self):
        self.application.upstream_manager.update_upstream(Upstream('no_available_backend', {}, []))

        request = self.post_url('no_available_backend', self.request.path)
        check_all_requests_done(self, 'no_available_backend')

        result = await request

        if result.failed and result.response.code == 502:
            self.text = 'no backend available'
            return

        self.text = result.text

        check_all_requests_done(self, 'no_available_backend')

    async def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
