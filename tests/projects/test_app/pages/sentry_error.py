from functools import partial

import sentry_sdk
from tornado.ioloop import IOLoop
from tornado.web import HTTPError

from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        ip = self.get_argument('ip', None)
        extra = self.get_argument('extra_key', None)
        if ip and extra:
            sentry_sdk.set_user({'real_ip': ip})
            sentry_sdk.set_extra('extra_key', extra)

        msg = 'My_sentry_exception'
        raise Exception(msg)

    async def post_page(self):
        raise HTTPError(500, 'my_HTTPError')

    async def put_page(self):
        sentry_sdk.set_extra('extra_key', 'extra_value')
        sentry_sdk.capture_message('sentry_message')

    def finish(self, chunk=None):
        # delay page finish to make sure that sentry mock got the exception
        self.add_timeout(IOLoop.current().time() + 0.3, partial(super().finish, chunk))

    def initialize_sentry_logger(self):
        sentry_sdk.set_user({'id': '123456'})
