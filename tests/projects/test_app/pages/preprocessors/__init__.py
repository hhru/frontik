import asyncio
import time

from tornado.concurrent import Future

from frontik.handler import PageHandler
from frontik.preprocessors import preprocessor
from typing import Callable


def pp0(name: str) -> Callable:
    @preprocessor
    def pp(handler):
        handler.run.append(name)

    return pp


@preprocessor
async def pp1(handler):
    handler.run.append('pp1-before')

    ready_future: Future = Future()
    ready_future.set_result('pp1-between')
    result = await ready_future

    handler.run.append(result)

    wait_future: Future = Future()
    handler.add_timeout(time.time() + 0.1, lambda: wait_future.set_result('pp1-after'))
    result = await wait_future

    handler.run.append(result)


@preprocessor
async def pp2(handler):
    future: Future = Future()

    async def put_request() -> None:
        res = await handler.put_url(handler.request.host, handler.request.path)
        handler.json.put({'put_request_finished': True})
        future.set_result(res.data)

    handler.run_task(put_request())
    handler.run.append('pp2')
    handler.pp2_future = future

    await future


@preprocessor
async def pp3(handler):
    handler.run.append('pp3')
    result = await handler.pp2_future
    handler.json.put(result)


class Page(PageHandler):
    preprocessors = [pp0('pp01'), pp0('pp02')]

    def prepare(self):
        super().prepare()

        self.run: list[str] = []
        self.json.put({'run': self.run})

        self.add_postprocessor(self.postprocessor)

    @pp1
    @preprocessor([pp2, pp3])
    async def get_page(self):
        self.run.append('get_page')

    async def put_page(self):
        self.text = {'put_request_preprocessors': self.run}

    @staticmethod
    async def postprocessor(handler):
        handler.json.put({'postprocessor': True})
        await asyncio.sleep(0.1)
