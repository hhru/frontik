import asyncio
import logging
from typing import Optional

from tornado.concurrent import Future

async_logger = logging.getLogger('frontik.futures')


class AbortAsyncGroup(Exception):
    pass


# AsyncGroup will become legacy in future releases
# It will be replaced with FutureGroup
class AsyncGroup:
    def __init__(self, name: Optional[str] = None) -> None:
        self._finished = False
        self._name = name
        self._futures: list[Future] = []

    def add_future(self, future: Future) -> None:
        if self._finished:
            raise RuntimeError('finish group is finished')
        self._futures.append(future)

    async def finish(self) -> None:
        try:
            await asyncio.gather(*self._futures)
        finally:
            self._finished = True

    def done(self) -> bool:
        return self._finished

    def pending(self) -> bool:
        return not self._finished and len(self._futures) != 0

    def abort(self) -> None:
        for future in self._futures:
            if not future.done():
                future.cancel()
        self._finished = True

    def __str__(self):
        return f'AsyncGroup(name={self._name}, finished={self._finished})'
