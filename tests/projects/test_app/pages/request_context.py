from concurrent.futures import ThreadPoolExecutor
from functools import partial

from frontik import request_context
from frontik.handler import PageHandler


def _callback(name, handler, *args):
    handler.json.put({name: request_context.get_handler_name()})


class Page(PageHandler):
    async def get_page(self):
        def _waited_callback(name):
            return self.finish_group.add(partial(_callback, name, self))

        self.json.put({'page': request_context.get_handler_name()})

        self.add_callback(_waited_callback('callback'))

        ThreadPoolExecutor(1).submit(_waited_callback('executor'))

        self.run_task(self.run_coroutine())

        future = self.post_url(self.request.host, self.request.uri)
        self.add_future(future, _waited_callback('future'))

    async def run_coroutine(self):
        self.json.put({'coroutine_before_yield': request_context.get_handler_name()})

        await self.post_url(self.request.host, self.request.uri)

        self.json.put({'coroutine_after_yield': request_context.get_handler_name()})

    async def post_page(self):
        pass

    def __repr__(self):
        return 'request_context'
