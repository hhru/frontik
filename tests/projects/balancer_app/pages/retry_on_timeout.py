# coding=utf-8

from tornado.web import HTTPError

from frontik.handler import PageHandler
from frontik.futures import AsyncGroup

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done


class Page(PageHandler):
    def get_page(self):
        self.application.http_client_factory.register_upstream('retry_on_timeout', {},
                                                               [get_server(self, 'broken'), get_server(self, 'normal')])

        def check_requests_cb():
            check_all_requests_done(self, 'retry_on_timeout')

        async_group = AsyncGroup(check_requests_cb)

        def callback_post(text, response):
            if response.error or text is None:
                raise HTTPError(500)

            self.text = text

        self.delete_url('retry_on_timeout', self.request.path, callback=async_group.add(callback_post),
                        connect_timeout=0.1, request_timeout=0.3, max_timeout_tries=2)

    def delete_page(self):
        self.add_header('Content-Type', 'text/plain')
        self.text = 'result'
