from frontik import handler, media_types
from frontik.futures import AsyncGroup

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(handler.PageHandler):
    def get_page(self):
        server = get_server(self, 'normal')
        self.application.http_client_factory.register_upstream('no_available_backend', {}, [server])
        server.is_active = False

        def check_requests_cb():
            check_all_requests_done(self, 'no_available_backend')

        async_group = AsyncGroup(check_requests_cb)

        def callback_post(text, response):
            if response.error and response.code == 502:
                self.text = 'no backend available'
                return

            self.text = text

        self.post_url('no_available_backend', self.request.path, callback=async_group.add(callback_post))
        check_all_requests_done(self, 'no_available_backend')

    def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
