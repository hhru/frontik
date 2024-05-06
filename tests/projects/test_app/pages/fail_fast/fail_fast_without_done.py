from fastapi import HTTPException

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


class Page(PageHandler):
    async def get_page_fail_fast(self, failed_future):
        raise HTTPException(401)


@router.get('/fail_fast/fail_fast_without_done', cls=Page)
async def get_page(handler=get_current_handler()):
    await handler.post_url(handler.get_header('host'), handler.path, fail_fast=True)


@router.post('/fail_fast/fail_fast_without_done', cls=Page)
async def post_page():
    raise HTTPException(403)
