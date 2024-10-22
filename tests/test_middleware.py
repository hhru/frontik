from fastapi import Request

from frontik.routing import regex_router, router
from frontik.testing import FrontikTestBase


@router.get('/qqq')
async def simple_page() -> str:
    return 'ok'


class TestMiddleware(FrontikTestBase):
    async def test_qqq(self):
        response = await self.fetch('/qqq')
        assert response.status_code == 200
