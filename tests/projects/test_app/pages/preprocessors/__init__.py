import asyncio
import time

from tornado.concurrent import Future
from tornado.web import HTTPError

from frontik.handler import PageHandler
from frontik.preprocessors import preprocessor


def pp0(name):
    @preprocessor
    async def pp(handler):
        handler.run.append(name)

    return pp


@preprocessor
async def pp_await_future(handler):
    handler.run.append('pp1-before')

    ready_future = Future()
    ready_future.set_result('pp1-between')
    result = await ready_future

    handler.run.append(result)

    wait_future = Future()
    handler.add_timeout(time.time() + 0.1, lambda: wait_future.set_result('pp1-after'))
    result = await wait_future

    handler.run.append(result)


@preprocessor
async def pp_waited_callback(handler):
    def _cb(_, __):
        handler.json.put({'put_request_finished': True})

    future = handler.put_url(handler.request.host, handler.request.path, callback=_cb)
    handler.run.append('pp2')
    handler.pp2_future = future

    await future


@preprocessor
async def pp_not_waited_callback(handler):
    def _cb(_, __):
        if handler.get_argument('raise_error_in_callback', 'false') == 'true':
            raise HTTPError(403)

    handler.run.append('pp3')
    handler.json.put(handler.pp2_future.result())
    handler.put_url(handler.request.host, handler.request.path, callback=_cb)


class Page(PageHandler):
    preprocessors = [pp0('pp01'), pp0('pp02')]

    def prepare(self):
        super().prepare()

        self.run = []
        self.json.put({
            'run': self.run
        })

        self.add_postprocessor(self.postprocessor)

    @pp_await_future
    @preprocessor([pp_waited_callback, pp_not_waited_callback])
    def get_page(self):
        self.run.append('get_page')

    def put_page(self):
        self.text = {'put_request_preprocessors': self.run}

    @staticmethod
    async def postprocessor(handler):
        handler.json.put({'postprocessor': True})
        await asyncio.sleep(0.1)
