# coding=utf-8

from tornado.web import HTTPError

from frontik.handler import PageHandler

from tests.projects.balancer_app import get_server


class Page(PageHandler):
    def get_page(self):
        free_server = get_server(self, 'free')
        free_server.rack = 'rack1'
        normal_server = get_server(self, 'normal')
        normal_server.rack = 'rack1'
        normal_server.datacenter = 'dc2'

        self.application.http_client_factory.register_upstream(
            'different_datacenter', {}, [free_server, normal_server])

        def callback(text, response):
            if free_server.requests != 1:
                raise HTTPError(500)

            if response.error and response.code == 502:
                self.text = 'no backend available'
                return

            self.text = text

        self.post_url('different_datacenter', self.request.path, callback=callback)

    def post_page(self):
        self.add_header('Content-Type', 'text/plain')
        self.text = 'result'
