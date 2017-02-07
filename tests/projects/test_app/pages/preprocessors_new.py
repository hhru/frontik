# coding=utf-8

from tornado.concurrent import Future

from frontik.handler import HTTPError, PageHandler
from frontik.preprocessors import preprocessor


def pp0(name):
    @preprocessor
    def pp(handler):
        handler.run.append(name)

    return pp


@preprocessor
def pp1(handler):
    handler.run.append('pp1-before-yield')

    done_future = Future()
    done_future.set_result('pp1-between-yield')
    result = yield done_future

    handler.run.append(result)

    self_uri = 'http://' + handler.request.host + handler.request.path
    post_result = yield handler.post_url(self_uri)

    if post_result.data.get('post'):
        handler.run.append('pp1-after-yield')


@preprocessor
def pp2(handler):
    self_uri = 'http://' + handler.request.host + handler.request.path
    future = handler.post_url(self_uri)
    handler.run.append('pp2')
    handler.json.put(future)

    if handler.get_argument('raise_error', 'false') != 'false':
        raise HTTPError(400)
    elif handler.get_argument('finish_with_postprocessors', 'false') != 'false':
        handler.finish_with_postprocessors()
    elif handler.get_argument('redirect', 'false') != 'false':
        handler.redirect(self_uri + '?redirected=true')
    elif handler.get_argument('finish', 'false') != 'false':
        handler.finish('finished')
    else:
        return future


@preprocessor
def pp3(handler):
    handler.run.append('pp3')


class Page(PageHandler):
    preprocessors = [pp0('pp01'), pp0('pp02')]

    def prepare(self):
        super(Page, self).prepare()

        self._use_new_preprocessors = True

        self.run = []
        self.json.put({
            'run': self.run
        })

        self.add_early_postprocessor(self.postprocessor)

    @pp1
    @preprocessor([pp2, pp3])
    def get_page(self):
        if self.get_argument('redirected', 'false') != 'false':
            self.json.replace({'redirected': True})
            return

        self.run.append('get_page')

    def post_page(self):
        self.text = {'post': self.run}

    @staticmethod
    def postprocessor(handler, callback):
        handler.json.put({'postprocessor': True})
        callback()
