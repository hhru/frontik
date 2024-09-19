import asyncio
import json

from frontik.handler import PageHandler
from frontik.loggers import JSON_FORMATTER
from frontik.routing import plain_router
from frontik.testing import FrontikTestBase

known_loggers = ['handler', 'stages']


@plain_router.get('/request_id', cls=PageHandler)
async def request_id_page() -> None:
    pass


@plain_router.get('/request_id_long', cls=PageHandler)
async def request_id_long_page() -> None:
    await asyncio.sleep(2)


@plain_router.get('/asgi_request_id')
async def asgi_request_id_page() -> None:
    pass


@plain_router.get('/asgi_request_id_long')
async def asgi_request_id_long_page() -> None:
    await asyncio.sleep(2)


class TestRequestId(FrontikTestBase):
    async def test_request_id(self):
        response = await self.fetch('/request_id')

        assert response.status_code == 200
        assert len(response.headers.getall('X-Request-Id')) == 1

    async def test_asgi_request_id(self):
        response = await self.fetch('/asgi_request_id')

        assert response.status_code == 200
        assert len(response.headers.getall('X-Request-Id')) == 1

    async def test_request_id_canceled_request(self, caplog):
        caplog.handler.setFormatter(JSON_FORMATTER)
        response = await self.fetch('/request_id_long', request_timeout=0.1)
        await asyncio.sleep(1)

        assert response.status_code == 599
        assert 'client has canceled request' in caplog.text

        rid = None
        for log_row in caplog.text.split('\n'):
            if log_row == '':
                continue
            log_obj = json.loads(log_row)
            assert log_obj.get('logger') in known_loggers

            mdc = log_obj.get('mdc')
            assert mdc is not None

            assert mdc.get('rid') is not None
            rid = rid or mdc.get('rid')
            assert mdc.get('rid') == rid

    async def test_asgi_request_id_canceled_request(self, caplog):
        caplog.handler.setFormatter(JSON_FORMATTER)
        response = await self.fetch('/asgi_request_id_long', request_timeout=0.1)
        await asyncio.sleep(1)

        assert response.status_code == 599
        assert 'client has canceled request' in caplog.text

        rid = None
        for log_row in caplog.text.split('\n'):
            if log_row == '':
                continue
            log_obj = json.loads(log_row)
            assert log_obj.get('logger') in known_loggers

            mdc = log_obj.get('mdc')
            assert mdc is not None

            assert mdc.get('rid') is not None
            rid = rid or mdc.get('rid')
            assert mdc.get('rid') == rid
