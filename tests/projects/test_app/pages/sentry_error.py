from functools import partial

from tornado.ioloop import IOLoop
from tornado.web import HTTPError

from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        ip = self.get_argument('ip', None)
        extra = self.get_argument('extra_key', None)
        if ip or extra:
            sentry_logger = self.get_sentry_logger()
            sentry_logger.update_user_info(ip=ip)
            sentry_logger.set_request_extra_data({'extra_key': extra})

        raise Exception('My_sentry_exception')

    async def post_page(self):
        raise HTTPError(500, 'my_HTTPError')

    async def put_page(self):
        sentry_logger = self.get_sentry_logger()
        sentry_logger.set_request_extra_data({'extra_key': 'extra_value'})
        sentry_logger.capture_message('sentry_message')

    def finish(self, chunk=None):
        # delay page finish to make sure that sentry mock got the exception
        self.add_timeout(IOLoop.current().time() + 0.3, partial(super().finish, chunk))

    def initialize_sentry_logger(self, sentry_logger):
        sentry_logger.update_user_info(user_id='123456')
