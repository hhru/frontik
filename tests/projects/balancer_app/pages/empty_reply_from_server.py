from frontik import handler, media_types

from tests.projects.balancer_app import get_server


class Page(handler.PageHandler):
    def get_page(self):
        self.application.http_client_factory.register_upstream('empty_reply_from_server', {},
                                                               [get_server(self, 'exit'), get_server(self, 'normal')])

        def callback_post(text, response):
            if response.error or response.code != 200:
                self.text = 'error'
                return

            self.text = text

        self.post_url('empty_reply_from_server', self.request.path, callback=callback_post)

    def post_page(self):
        self.add_header('Content-Type', media_types.TEXT_PLAIN)
        self.text = 'result'
