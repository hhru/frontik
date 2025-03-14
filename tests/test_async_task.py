import asyncio

import pytest

from frontik.app import FrontikApplication
from frontik.loggers import JSON_FORMATTER
from frontik.routing import router
from frontik.testing import FrontikTestBase
from frontik.util import run_async_task


@router.get('/async_task_exception')
async def some_exception_page() -> None:
    async def _async_task() -> None:
        raise Exception('test _async_task exception')

    run_async_task(_async_task())


class TestAsyncTask(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

    async def test_some_exception(self, caplog):
        caplog.handler.setFormatter(JSON_FORMATTER)
        response = await self.fetch('/async_task_exception')
        await asyncio.sleep(0.1)
        assert response.status_code == 200

        for log_row in caplog.text.split('\n'):
            if log_row == '':
                continue

            if 'test _async_task exception' in log_row:
                break
        else:
            assert False, 'exception was not found in logs'
