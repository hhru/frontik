from frontik.handler import FinishWithPostprocessors, PageHandler
from frontik.preprocessors import preprocessor


@preprocessor
def pp1(handler):
    handler.set_header('content-type', 'text/plain')


@preprocessor
def pp2(handler):
    async def pp2_coro() -> None:
        await handler.post_url(handler.request.host, handler.request.uri + '&from=pp')

        if handler.get_argument('finish', None):
            handler.set_status(400)
            handler.finish('DONE_IN_PP')

        elif handler.get_argument('abort', None):
            raise FinishWithPostprocessors

    handler.add_preprocessor_future(pp2_coro())


class Page(PageHandler):
    @pp1
    @pp2
    async def get_page(self):
        # Page handler method must not be called
        self.set_status(404)

    @pp1
    async def post_page(self):
        pass
