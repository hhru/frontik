import asyncio
from asyncio import Future
from typing import Optional

from frontik.integrations import Integration
from frontik.options import options


class IntegrationTestException(Exception):
    pass


class LongFailingIntegration(Integration):

    def initialize_app(self, app) -> Optional[Future]:
        return asyncio.ensure_future(self.sleep_and_raise_if_needed())

    @staticmethod
    async def sleep_and_raise_if_needed():
        if options.fail_test_integration:
            await asyncio.sleep(1)
            raise IntegrationTestException

    def initialize_handler(self, handler):
        pass
