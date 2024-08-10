import asyncio
from typing import Callable

from tornado.concurrent import Future

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router
from frontik.util import gather_dict


async def delayed(callback: Callable) -> None:
    await asyncio.sleep(0.3)
    callback()


class Page(PageHandler):
    def get_future(self, result: str, exception: bool = False) -> Future:
        future: Future = Future()

        def _finish_future():
            if exception:
                future.set_exception(ValueError('Some error'))
            else:
                future.set_result(result)

        asyncio.create_task(delayed(_finish_future))
        return future


@plain_router.get('/fail_fast/future', cls=Page)
async def get_page(handler=get_current_handler()):
    fail_future = handler.get_query_argument('fail_future', 'false') == 'true'

    results = await gather_dict({'future': handler.get_future('future_result', exception=fail_future)})

    handler.json.put(results)
