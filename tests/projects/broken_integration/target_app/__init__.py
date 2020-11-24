import asyncio

from frontik.app import FrontikApplication


class TestApplication(FrontikApplication):

    async def init(self):
        await super().init()
        await self.broken_future()

    async def broken_future(self):
        await asyncio.sleep(1)
        raise Exception
