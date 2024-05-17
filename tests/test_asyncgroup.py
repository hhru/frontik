import asyncio
import logging

import pytest

from frontik.futures import AsyncGroup

logging.root.setLevel(logging.NOTSET)


class TestAsyncGroup:
    async def test_exception_in_first(self) -> None:
        async def callback1() -> None:
            raise Exception('callback1 error')

        async def callback2() -> None:
            await asyncio.sleep(0)

        ag = AsyncGroup(name='test_group')
        ag.add_future(asyncio.create_task(callback1()))
        ag.add_future(asyncio.create_task(callback2()))

        with pytest.raises(Exception, match='callback1 error'):
            await ag.finish()

        assert ag.done() is True

    async def test_exception_in_last(self) -> None:
        async def callback1() -> None:
            await asyncio.sleep(0)

        async def callback2() -> None:
            raise Exception('callback2 error')

        ag = AsyncGroup(name='test_group')
        ag.add_future(asyncio.create_task(callback1()))
        ag.add_future(asyncio.create_task(callback2()))

        with pytest.raises(Exception, match='callback2 error'):
            await ag.finish()

        assert ag.done() is True
