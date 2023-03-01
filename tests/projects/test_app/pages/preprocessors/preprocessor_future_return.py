from frontik.handler import PageHandler
from frontik.preprocessors import preprocessor

from tornado.concurrent import Future


@preprocessor
async def pp1(handler):
    handler.future = Future()
    await handler.post_url(handler.request.host, handler.request.uri)
    handler.future.set_result(True)
    handler.future_result = 'test'


@preprocessor
async def pp2(handler):
    await handler.future
    handler.json.put({
        'test': handler.future_result
    })


class Page(PageHandler):
    @pp1
    @pp2
    async def get_page(self):
        pass

    async def post_page(self):
        pass
