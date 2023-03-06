from tornado.web import HTTPError

from frontik.handler import FinishWithPostprocessors, HTTPErrorWithPostprocessors, PageHandler
from frontik.preprocessors import preprocessor


@preprocessor
def pp_before(handler):
    handler.run.append('before')


@preprocessor
async def pp(handler):
    async def post_request():
        await handler.put_url(handler.request.host, handler.request.path)
        handler.json.put({'put_request_finished': True})

    future = handler.run_task(post_request())
    handler.run.append('pp')

    if handler.get_argument('raise_error', 'false') != 'false':
        raise HTTPError(400)
    elif handler.get_argument('raise_custom_error', 'false') != 'false':
        handler.json.replace({'custom_error': True})
        raise HTTPErrorWithPostprocessors(400)
    elif handler.get_argument('abort_preprocessors', 'false') != 'false':
        raise FinishWithPostprocessors(wait_finish_group=True)
    elif handler.get_argument('abort_preprocessors_nowait', 'false') != 'false':
        raise FinishWithPostprocessors(wait_finish_group=False)
    elif handler.get_argument('redirect', 'false') != 'false':
        handler.redirect(handler.request.host + handler.request.path + '?redirected=true')
    elif handler.get_argument('finish', 'false') != 'false':
        handler.finish('finished')
    else:
        await future


@preprocessor
def pp_after(handler):
    handler.run.append('after')


class Page(PageHandler):
    def prepare(self):
        super().prepare()

        self.run = []
        self.json.put({
            'run': self.run
        })

        self.add_postprocessor(lambda handler: handler.json.put({'postprocessor': True}))

    @pp_before
    @pp
    @pp_after
    async def get_page(self):
        self.run.append('get_page')

    async def put_page(self):
        pass
