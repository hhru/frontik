# coding=utf-8

from tornado.concurrent import Future

from frontik.handler import FinishWithPostprocessors, HTTPError, PageHandler, preprocessor


@preprocessor
def pp1(handler):
    handler.run.append('pp1')

    f = Future()
    f.set_result('pp1')
    return f


@preprocessor
def pp2(handler):
    future = handler.post_url(handler.request.host + handler.request.path)
    handler.run.append('pp2')
    handler.json.put(future)

    if handler.get_argument('raise_error', 'false') != 'false':
        raise HTTPError(400)

    return future


@preprocessor
def pp3(handler):
    handler.run.append('pp3')

    if handler.get_argument('raise_finish', 'false') != 'false':
        raise FinishWithPostprocessors()


@PageHandler.add_preprocessor
def oldstyle_pp(handler, callback):
    handler.run.append('oldstyle_pp')
    callback()


class Page(PageHandler):
    def prepare(self):
        super(Page, self).prepare()

        self.run = []
        self.json.put({
            'run': self.run
        })

    @pp1
    @preprocessor([pp2, pp3])
    @oldstyle_pp
    def get_page(self):
        self.run.append('get_page')

    def post_page(self):
        self.text = {'post': True}
