# coding=utf-8

import weakref

import tornado.options

import frontik.handler


class PageHandlerActiveLimit(object):
    working_handlers_count = 0

    def __init__(self, handler):
        self.handler = weakref.proxy(handler)
        self.acquired = False

        if PageHandlerActiveLimit.working_handlers_count <= tornado.options.options.handlers_count:
            self.handler.log.debug(
                'started {0} {1} (handlers_count = {2})'.format(
                    self.handler.request.method, self.handler.request.uri, PageHandlerActiveLimit.working_handlers_count
                )
            )
        else:
            self.handler.log.warn(
                'dropping {0} {1}: too many handlers ({2})'.format(
                    self.handler.request.method, self.handler.request.uri, PageHandlerActiveLimit.working_handlers_count
                )
            )

            raise frontik.handler.HTTPError(503)

        self.acquire()

    def acquire(self):
        if not self.acquired:
            PageHandlerActiveLimit.working_handlers_count += 1
            self.acquired = True
            self.handler.log.debug('workers count+1 = {0}'.format(PageHandlerActiveLimit.working_handlers_count))

    def release(self):
        if self.acquired:
            PageHandlerActiveLimit.working_handlers_count -= 1
            self.acquired = False
            self.handler.log.debug('workers count-1 = {0}'.format(PageHandlerActiveLimit.working_handlers_count))
