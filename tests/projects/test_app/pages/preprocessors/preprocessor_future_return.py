from frontik.handler import PageHandler
from frontik.preprocessors import preprocessor


@preprocessor
def pp1(handler):
    def _cb(_, __):
        handler.future_result = 'test'

    handler.future = handler.add_preprocessor_future(
        handler.post_url(handler.request.host, handler.request.uri, callback=_cb)
    )


@preprocessor
def pp2(handler):
    yield handler.future
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
