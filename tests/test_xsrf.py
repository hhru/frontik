from collections.abc import Generator

import pytest

from frontik.app import FrontikApplication
from frontik.options import options
from frontik.routing import router
from frontik.testing import FrontikTestBase


@router.post('/check_xsrf')
async def check_xsrf() -> None:
    pass


class TestCheckXsrf(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> Generator[FrontikApplication]:
        options.xsrf_cookies = True
        yield FrontikApplication(app_module_name=None)
        options.xsrf_cookies = False

    async def test_check_xsrf(self) -> None:
        response = await self.fetch('/check_xsrf', method='POST')
        assert response.status_code == 403

        response = await self.fetch('/check_xsrf', method='POST', data={'_xsrf': 'super_token'})
        assert response.status_code == 403

        response = await self.fetch(
            '/check_xsrf',
            method='POST',
            data={'_xsrf': 'super_token'},
            headers={'Cookie': '_xsrf=super_token'},
        )
        assert response.status_code == 200
