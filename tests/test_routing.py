from fastapi import Request
from frontik.routing import router, regex_router
from frontik.testing import FrontikTestBase


@router.get('/simple')
async def get_page1():
    return 'ok'


@regex_router.get('/id/(?P<id>[^/]+)')
async def get_page(request: Request) -> None:
    return request.path_params.get('id')


@router.get('/nested/nested/nested')
async def get_page():
    return 'OK'


class TestRouting(FrontikTestBase):
    async def test_extra_slash_in_mapping(self):
        response = await self.fetch('//not_simple')
        assert response.status_code == 404

    async def test_rewrite_single(self):
        response = await self.fetch('/id/some')
        assert response.data == 'some'

    async def test_rewrite_multiple(self) -> None:
        response = await self.fetch('/id/some,another')
        assert response.data == 'some,another'

    async def test_not_found(self):
        response = await self.fetch('/not_exists')
        assert response.status_code == 404

    async def test_filemapping_404_on_dot_in_url(self):
        response = await self.fetch('/nested/nested.nested')
        assert response.status_code == 404
