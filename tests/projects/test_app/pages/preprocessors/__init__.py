import time

from tornado import gen
from tornado.concurrent import Future

from frontik.handler import PageHandler
from frontik.preprocessors import preprocessor


def pp0(name):
    @preprocessor
    def pp(handler):
        handler.run.append(name)

    return pp


@preprocessor
def pp1(handler):
    handler.run.append('pp1-before')

    ready_future = Future()
    ready_future.set_result('pp1-between')
    result = yield ready_future

    handler.run.append(result)

    wait_future = Future()
    handler.add_timeout(time.time() + 0.1, lambda: wait_future.set_result('pp1-after'))
    result = yield wait_future

    handler.run.append(result)


@preprocessor
def pp2(handler):
    def _cb(_, __):
        handler.json.put({'put_request_finished': True})

    future = handler.put_url(handler.request.host, handler.request.path, callback=_cb)
    handler.run.append('pp2')
    handler.pp2_future = future

    yield future


@preprocessor
def pp3(handler):
    handler.run.append('pp3')
    handler.json.put(handler.pp2_future.result())


class Page(PageHandler):
    preprocessors = [pp0('pp01'), pp0('pp02')]

    def prepare(self):
        super().prepare()

        self.run = []
        self.json.put({
            'run': self.run
        })

        self.add_postprocessor(self.postprocessor)

    @pp1
    @preprocessor([pp2, pp3])
    def get_page(self):
        self.run.append('get_page')

    def put_page(self):
        self.text = {'put_request_preprocessors': self.run}

    @staticmethod
    def postprocessor(handler):
        handler.json.put({'postprocessor': True})
        yield gen.sleep(0.1)
