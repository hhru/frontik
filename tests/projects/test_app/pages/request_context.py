import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from fastapi import Request

from frontik import request_context
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


def _callback(name, handler, *args):
    handler.json.put({name: request_context.get_handler_name()})


class Page(PageHandler):
    async def run_coroutine(self, host: str) -> None:
        self.json.put({'coroutine_before_yield': request_context.get_handler_name()})

        await self.post_url(host, self.path)

        self.json.put({'coroutine_after_yield': request_context.get_handler_name()})

    def __repr__(self):
        return 'request_context'


@router.get('/request_context', cls=Page)
async def get_page(request: Request, handler: Page = get_current_handler()) -> None:
    def _waited_callback(name: str) -> Callable:
        return handler.finish_group.add(partial(_callback, name, handler))

    handler.json.put({'page': request_context.get_handler_name()})

    dumb_task = asyncio.create_task(asyncio.sleep(0))
    dumb_task.add_done_callback(_waited_callback('callback'))

    ThreadPoolExecutor(1).submit(_waited_callback('executor'))

    handler.run_task(handler.run_coroutine(request.headers.get('host', '')))

    async def make_request() -> None:
        await handler.post_url(request.headers.get('host', ''), handler.path)

    future = asyncio.create_task(make_request())
    future.add_done_callback(_waited_callback('future'))


@router.post('/request_context', cls=Page)
async def post_page():
    pass
