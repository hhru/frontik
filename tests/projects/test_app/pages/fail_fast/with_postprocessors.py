from tornado.web import HTTPError

from frontik.handler import HTTPErrorWithPostprocessors, PageHandler, get_current_handler
from frontik.routing import router


class Page(PageHandler):
    def get_page_fail_fast(self, failed_future):
        self.json.put({'error': 'some_error'})
        raise HTTPErrorWithPostprocessors(502)


@router.get('/fail_fast/with_postprocessors', cls=Page)
async def get_page(handler=get_current_handler()):
    result = await handler.post_url(handler.get_header('host'), handler.path, fail_fast=True)
    handler.json.put(result.data)


@router.post('/fail_fast/with_postprocessors', cls=Page)
async def post_page():
    raise HTTPError(403)
