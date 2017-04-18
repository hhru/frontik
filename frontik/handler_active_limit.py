# coding=utf-8

import logging

from tornado.options import options

import frontik.handler

handler_limit_logger = logging.getLogger('frontik.handler_active_limit')


class PageHandlerActiveLimit(object):
    working_handlers_count = 0

    def __init__(self, request):
        self.acquired = False

        if PageHandlerActiveLimit.working_handlers_count > options.handlers_count:
            handler_limit_logger.warning(
                'dropping %s %s: too many handlers (%d)',
                request.method, request.uri, PageHandlerActiveLimit.working_handlers_count
            )

            raise frontik.handler.HTTPError(503)

        self.acquire()

    def acquire(self):
        if not self.acquired:
            PageHandlerActiveLimit.working_handlers_count += 1
            self.acquired = True
            handler_limit_logger.info('handlers count + 1 = %d', PageHandlerActiveLimit.working_handlers_count)

    def release(self):
        if self.acquired:
            PageHandlerActiveLimit.working_handlers_count -= 1
            self.acquired = False
            handler_limit_logger.info('handlers count - 1 = %d', PageHandlerActiveLimit.working_handlers_count)
