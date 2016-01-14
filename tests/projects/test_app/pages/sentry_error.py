# coding=utf-8

from functools import partial

from tornado.ioloop import IOLoop

from frontik.handler import HTTPError, PageHandler


class Page(PageHandler):
    def get_page(self):
        raise Exception('Runtime exception for Sentry')

    def post_page(self):
        raise HTTPError('HTTPError for Sentry')

    def put_page(self):
        self.get_sentry_logger().capture_message('Message for Sentry')

    def finish(self, chunk=None):
        # delay page finish to make sure that sentry mock got the exception
        self.add_timeout(IOLoop.instance().time() + 1.0, partial(super(Page, self).finish, chunk))

    def initialize_sentry_logger(self, sentry_logger):
        sentry_logger.update_user_info(user_id='123456')
