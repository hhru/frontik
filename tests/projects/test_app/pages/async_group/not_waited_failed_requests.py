from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


class Page(PageHandler):
    data: dict = {}

    def _record_failed_request(self, data: dict) -> None:
        Page.data.update(data)
        msg = 'Some error'
        raise ValueError(msg)


@router.get('/async_group/not_waited_failed_requests', cls=Page)
async def get_page(handler: Page = get_current_handler()) -> None:
    if not handler.data:
        host = handler.request.headers.get('host', '')
        # HTTP request with waited=False and fail_fast=True should not influence responses to client
        await handler.head_url(host, handler.path, waited=False, fail_fast=True)
        await handler.post_url(host, handler.path, waited=False, fail_fast=True)
        await handler.put_url(host, handler.path, waited=False, fail_fast=True)
        await handler.delete_url(host, handler.path, waited=False, fail_fast=True)

        handler.json.put({'get': True})
    else:
        handler.json.put(handler.data)
        handler.data = {}


@router.post('/async_group/not_waited_failed_requests', cls=Page)
async def post_page(handler: Page = get_current_handler()) -> None:
    handler._record_failed_request({'post_failed': True})


@router.put('/async_group/not_waited_failed_requests', cls=Page)
async def put_page(handler: Page = get_current_handler()) -> None:
    handler._record_failed_request({'put_failed': True})


@router.delete('/async_group/not_waited_failed_requests', cls=Page)
async def delete_page(handler: Page = get_current_handler()) -> None:
    handler._record_failed_request({'delete_failed': True})


@router.head('/async_group/not_waited_failed_requests', cls=Page)
async def head_page(handler: Page = get_current_handler()) -> None:
    handler._record_failed_request({'head_failed': True})
