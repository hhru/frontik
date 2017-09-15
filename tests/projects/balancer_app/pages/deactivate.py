# coding=utf-8

import frontik.handler
from tornado.ioloop import IOLoop

from tests.projects.balancer_app import get_server
from tests.projects.balancer_app.pages import check_all_requests_done, check_all_servers_occupied


class Page(frontik.handler.PageHandler):
    def get_page(self):
        server = get_server(self, 'free')
        self.application.http_client_factory.register_upstream(
            'deactivate', {'max_fails': 1, 'fail_timeout': 0.1}, [server])
        self.text = ''

        def check_server_active():
            if server.is_active:
                self.text += ' activated'

            check_all_requests_done(self, 'deactivate')

        def callback_post(_, response):
            if response.error and response.code == 502 and not server.is_active:
                self.text = 'deactivated'

            self.add_timeout(IOLoop.current().time() + 0.2,
                             self.finish_group.add(self.check_finished(check_server_active)))

        self.post_url('deactivate', self.request.path, callback=callback_post)

        check_all_servers_occupied(self, 'deactivate')
