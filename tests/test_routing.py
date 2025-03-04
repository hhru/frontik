import pytest
from fastapi import Request
from fastapi.routing import APIRoute

from frontik.app import FrontikApplication
from frontik.routing import get_route_sort_key, regex_router, router
from frontik.testing import FrontikTestBase


@router.get('/simple')
async def simple_page() -> str:
    return 'ok'


@router.api_route('/multiple', methods=['GET', 'POST'])
async def multi_method_page(request: Request) -> str:
    return request.method


@router.get('/simple_slash/')
async def simple_slash_page() -> str:
    return 'ok'


@regex_router.get('/id/(?P<id>[^/]+)')
async def id_page(request: Request) -> str:
    return str(request.path_params.get('id'))


@router.get('/nested/nested/nested')
async def nested_page() -> str:
    return 'OK'


class TestRouting(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

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

    async def test_ending_slash(self):
        response = await self.fetch('/simple')
        assert response.status_code == 200

        response = await self.fetch('/simple/')
        assert response.status_code == 200

        response = await self.fetch('/simple_slash/')
        assert response.status_code == 200

        response = await self.fetch('/simple_slash')
        assert response.status_code == 200

    def test_routes_sorting(self):
        def noop():
            pass

        routes = [
            APIRoute('/some/other/{thing2}', noop),
            APIRoute('/some/{other}/thing', noop),
            APIRoute('/some', noop),
            APIRoute('/some/other/{thing}', noop),
        ]
        routes.sort(key=get_route_sort_key)
        assert routes[0].path == '/some'
        assert routes[1].path == '/some/other/{thing2}'
        assert routes[2].path == '/some/other/{thing}'
        assert routes[3].path == '/some/{other}/thing'

    @pytest.mark.parametrize('method', ['GET', 'POST'])
    async def test_multiple_methods(self, method):
        response = await self.fetch('/multiple', method=method)
        assert response.status_code == 200
        assert response.data == method
