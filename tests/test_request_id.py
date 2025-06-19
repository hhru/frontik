import asyncio
import json

import pytest
from http_client.request_response import SERVER_TIMEOUT

from frontik.app import FrontikApplication
from frontik.loggers import JSON_FORMATTER
from frontik.routing import router
from frontik.testing import FrontikTestBase

known_loggers = ['handler', 'stages']


@router.get('/asgi_request_id')
async def asgi_request_id_page() -> None:
    pass


@router.get('/asgi_request_id_long')
async def asgi_request_id_long_page() -> None:
    await asyncio.sleep(2)


class TestRequestId(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

    async def test_asgi_request_id(self):
        response = await self.fetch('/asgi_request_id')

        assert response.status_code == 200
        assert len(response.headers.getall('X-Request-Id')) == 1

    async def test_asgi_request_id_canceled_request(self, caplog):
        caplog.handler.setFormatter(JSON_FORMATTER)
        response = await self.fetch('/asgi_request_id_long', request_timeout=0.1)
        await asyncio.sleep(1)

        assert response.status_code == SERVER_TIMEOUT
        assert 'client has canceled request' in caplog.text

        for log_row in caplog.text.split('\n'):
            if log_row == '':
                continue
            log_obj = json.loads(log_row)
            assert log_obj.get('logger') in known_loggers

            mdc = log_obj.get('mdc')
            assert mdc is not None
