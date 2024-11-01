import pytest
from fastapi import HTTPException

from frontik import media_types
from frontik.app import FrontikApplication
from frontik.routing import router
from frontik.testing import FrontikTestBase


@router.get('/http_exception')
async def get_page(code: int = 200) -> None:
    raise HTTPException(code)


class TestHttpError(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication()

    async def test_raise_200(self):
        response = await self.fetch('/http_exception?code=200')
        assert response.status_code == 200
        assert response.headers.get('content-type') == media_types.APPLICATION_JSON
        assert response.raw_body == b'{"detail":"OK"}'

    async def test_raise_401(self):
        response = await self.fetch('/http_exception?code=401')
        assert response.status_code == 401
        assert response.headers['content-type'] == media_types.APPLICATION_JSON
        assert response.raw_body == b'{"detail":"Unauthorized"}'

    async def test_405(self):
        response = await self.fetch('/http_exception', method='PUT')
        assert response.status_code == 405
        assert response.headers['allow'] == 'GET'
