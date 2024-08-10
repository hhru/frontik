from tornado.web import HTTPError

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


class Page(PageHandler):
    def get_page_fail_fast(self, failed_future):
        raise HTTPError(401)


@plain_router.get('/fail_fast/fail_fast_without_done', cls=Page)
async def get_page(handler=get_current_handler()):
    await handler.post_url(handler.get_header('host'), handler.path, fail_fast=True)


@plain_router.post('/fail_fast/fail_fast_without_done', cls=Page)
async def post_page():
    raise HTTPError(403)
