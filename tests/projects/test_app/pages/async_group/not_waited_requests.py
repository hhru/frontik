import asyncio

from fastapi import Request

from frontik.handler import AbortAsyncGroup, PageHandler, get_current_handler
from frontik.routing import router


class Page(PageHandler):
    data: dict = {}

    async def coro(self, host: str) -> None:
        await self.post_url(host, self.path, waited=False)

        # HTTP requests with waited=True are aborted after handler is finished
        try:
            await self.delete_url(host, self.path, waited=True)
        except AbortAsyncGroup:
            self.record_request({'delete_cancelled': True})

    def record_request(self, data: dict) -> None:
        self.json.put(data)
        Page.data.update(data)


@router.get('/async_group/not_waited_requests', cls=Page)
async def get_page(request: Request, handler: Page = get_current_handler()) -> None:
    if not handler.data:
        handler.json.put({'get': True})
        asyncio.create_task(handler.coro(request.headers.get('host', '')))
    else:
        while not all(x in handler.data for x in ('post_made', 'delete_cancelled')):
            await asyncio.sleep(0.05)

        handler.json.put(handler.data)
        handler.data = {}


@router.post('/async_group/not_waited_requests', cls=Page)
async def post_page(handler=get_current_handler()):
    handler.record_request({'post_made': True})


@router.put('/async_group/not_waited_requests', cls=Page)
async def put_page(handler=get_current_handler()):
    handler.record_request({'put_made': True})


@router.delete('/async_group/not_waited_requests', cls=Page)
async def delete_page(handler=get_current_handler()):
    handler.record_request({'delete_made': True})
