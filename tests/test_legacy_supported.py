from fastapi import Request

from frontik.routing import router
from frontik.testing import FrontikTestBase


@router.get('/legacy_supported')
async def legacy_supported_page(request: Request) -> bool:
    return (
        request['debug_mode'] is not None
        and request['tornado_request'] is not None
        and request['frontik_app'] is not None
    )


class TestLegacySupported(FrontikTestBase):
    async def test_config(self):
        response = await self.fetch('/legacy_supported')

        assert response.status_code == 200
        assert response.raw_body == b'true'
