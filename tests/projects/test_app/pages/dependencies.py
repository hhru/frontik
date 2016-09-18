# coding=utf-8

from tornado.concurrent import Future

from frontik.async import dependency
from frontik.handler import PageHandler


@dependency
def dep1(handler):
    handler.run.append('dep1')

    f = Future()
    f.set_result('dep1')
    return f


@dependency
def dep2(handler):
    future = handler.post_url(handler.request.host + handler.request.path)
    handler.run.append('dep2')
    handler.json.put(future)
    return future


@dependency
def dep3(handler):
    handler.run.append('dep3')


@PageHandler.add_preprocessor
def dep4(handler, callback):
    handler.run.append('dep4')
    callback()


class Page(PageHandler):
    def __init__(self, application, request, logger, **kwargs):
        super(Page, self).__init__(application, request, logger, **kwargs)
        self.run = []

    @dep1
    @dependency([dep2, dep3])
    @dep4
    def get_page(self):
        self.json.put({
            'run': self.run
        })

    def post_page(self):
        self.json.put({
            'post': True
        })
