# coding=utf-8

from tornado.web import HTTPError

from frontik.handler import PageHandler
from frontik.futures import AsyncGroup

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


class Page(PageHandler):
    def get_page(self):
        self.application.http_client_factory.register_upstream('retry_error', {},
                                                               [get_server(self, 'broken'), get_server(self, 'normal')])
        self.text = ''

        def check_requests_cb():
            check_all_requests_done(self, 'retry_error')

        async_group = AsyncGroup(check_requests_cb)

        def callback(text, response):
            if response.error or text is None:
                raise HTTPError(500)

            self.text = self.text + text

        self.put_url('retry_error', self.request.path, callback=async_group.add(callback))
        self.put_url('retry_error', self.request.path, callback=async_group.add(callback))
        self.put_url('retry_error', self.request.path, callback=async_group.add(callback))

        check_all_servers_occupied(self, 'retry_error')

    def put_page(self):
        self.add_header('Content-Type', 'text/plain')
        self.text = 'result'
