# coding=utf-8

from tornado.web import HTTPError

from frontik.handler import PageHandler

from tests.projects.balancer_app import get_server


class Page(PageHandler):
    def get_page(self):
        free_server = get_server(self, 'free')
        free_server.rack = 'rack1'
        normal_server_1 = get_server(self, 'normal')
        normal_server_1.weight = 100
        normal_server_1.rack = 'rack1'
        normal_server_2 = get_server(self, 'normal')
        normal_server_2.weight = 1
        normal_server_2.rack = 'rack2'

        self.application.http_client_factory.register_upstream(
            'retry_to_different_rack', {}, [free_server, normal_server_1, normal_server_2])

        def callback_retry_to_different_rack(text, response):
            if response.error or text is None:
                raise HTTPError(500)

            requests = (free_server.requests, normal_server_1.requests, normal_server_2.requests)
            if requests != (1, 0, 1):
                raise HTTPError(500)

            self.text = text

        self.post_url('retry_to_different_rack', self.request.path, callback=callback_retry_to_different_rack)

    def post_page(self):
        self.add_header('Content-Type', 'text/plain')
        self.text = 'result'
