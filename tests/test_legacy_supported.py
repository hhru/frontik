import pytest
from fastapi import Request

from frontik.app import FrontikApplication
from frontik.routing import router
from frontik.testing import FrontikTestBase


@router.get('/legacy_supported')
async def legacy_supported_page(request: Request) -> bool:
    return request['debug_mode'] is not None and request['frontik_app'] is not None


class TestLegacySupported(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

    async def test_config(self):
        response = await self.fetch('/legacy_supported')

        assert response.status_code == 200
        assert response.raw_body == b'true'
