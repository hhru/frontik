import asyncio

import requests

from frontik.app import FrontikApplication
from frontik.options import options


class TestApplication(FrontikApplication):

    def init_async(self):
        default_init_futures = super().init_async()
        return [asyncio.ensure_future(self.broken_future()), *default_init_futures]

    async def broken_future(self):
        await asyncio.sleep(1)
        raise Exception
