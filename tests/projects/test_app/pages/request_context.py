from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from frontik import request_context
from frontik.handler import PageHandler, router


def _callback(name, handler, *args):
    handler.json.put({name: request_context.get_handler_name()})


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        def _waited_callback(name: str) -> Callable:
            return self.finish_group.add(partial(_callback, name, self))

        self.json.put({'page': request_context.get_handler_name()})

        self.add_callback(_waited_callback('callback'))

        ThreadPoolExecutor(1).submit(_waited_callback('executor'))

        self.run_task(self.run_coroutine())

        future = self.post_url(self.request.host, self.request.uri)  # type: ignore
        self.add_future(future, _waited_callback('future'))

    async def run_coroutine(self) -> None:
        self.json.put({'coroutine_before_yield': request_context.get_handler_name()})

        await self.post_url(self.request.host, self.request.uri)  # type: ignore

        self.json.put({'coroutine_after_yield': request_context.get_handler_name()})

    @router.post()
    async def post_page(self):
        pass

    def __repr__(self):
        return 'request_context'
