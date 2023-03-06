from functools import partial

from tornado.ioloop import IOLoop
from tornado.web import HTTPError

from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        raise Exception('Runtime exception for Sentry')

    async def post_page(self):
        raise HTTPError(500, 'HTTPError for Sentry')

    async def put_page(self):
        self.get_sentry_logger().capture_message('Message for Sentry')

    def finish(self, chunk=None):
        # delay page finish to make sure that sentry mock got the exception
        self.add_timeout(IOLoop.current().time() + 0.3, partial(super().finish, chunk))

    def initialize_sentry_logger(self, sentry_logger):
        sentry_logger.update_user_info(user_id='123456')
