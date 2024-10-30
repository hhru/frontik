import pytest
from fastapi import Response

from frontik.app import FrontikApplication
from frontik.routing import router
from frontik.testing import FrontikTestBase


@router.get('/cookies')
async def cookies_page(response: Response) -> None:
    response.set_cookie('key1', 'val1')
    response.set_cookie('key2', 'val2')


class TestCookies(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication()

    async def test_cookies(self):
        response = await self.fetch('/cookies')

        assert response.status_code == 200
        assert response.headers.getall('Set-Cookie') == [
            'key1=val1; Path=/; SameSite=lax',
            'key2=val2; Path=/; SameSite=lax',
        ]
