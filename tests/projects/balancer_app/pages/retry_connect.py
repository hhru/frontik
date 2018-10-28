# coding=utf-8

from tornado.web import HTTPError

from frontik.handler import PageHandler
from frontik.futures import AsyncGroup

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


class Page(PageHandler):
    def get_page(self):
        self.application.http_client_factory.register_upstream('retry_connect', {},
                                                               [get_server(self, 'free'), get_server(self, 'normal')])
        self.text = ''

        def check_requests_cb():
            check_all_requests_done(self, 'retry_connect')

        async_group = AsyncGroup(check_requests_cb)

        def callback_post(text, response):
            if response.error or text is None:
                raise HTTPError(500)

            self.text = self.text + text

        self.post_url('retry_connect', self.request.path, callback=async_group.add(callback_post))
        self.post_url('retry_connect', self.request.path, callback=async_group.add(callback_post))
        self.post_url('retry_connect', self.request.path, callback=async_group.add(callback_post))

        check_all_servers_occupied(self, 'retry_connect')

    def post_page(self):
        self.add_header('Content-Type', 'text/plain')
        self.text = 'result'
