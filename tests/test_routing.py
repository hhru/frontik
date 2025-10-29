import pytest
from fastapi import Request
from fastapi.routing import APIRoute

from frontik.app import FrontikApplication
from frontik.routing import get_route_sort_key, router
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


@router.get('/id/{id}')
async def id_page(request: Request) -> str:
    return str(request.path_params.get('id'))


@router.get('/nested/nested/nested')
async def nested_page() -> str:
    return 'OK'


@router.options('/simple_options')
async def simple_preflight_options() -> str:
    return 'preflight ok'


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

    async def test_options_request_on_existing_route(self) -> None:
        response = await self.fetch('/simple', method='OPTIONS')
        assert response.status_code == 204

    async def test_options_request_on_undefined_route(self) -> None:
        response = await self.fetch('/nonexistent_route', method='OPTIONS')
        assert response.status_code == 204

    async def test_options_request_on_defined_route(self) -> None:
        response = await self.fetch('/simple_options', method='OPTIONS')
        assert response.data == 'preflight ok'


def create_mock_route(path: str) -> APIRoute:
    return APIRoute(path, endpoint=lambda: None, methods=['GET'])


class TestRoutingOrder:
    def test_exact_routes_before_param_routes(self) -> None:
        routes = [
            create_mock_route('/{param}'),
            create_mock_route('/specific'),
        ]
        sorted_routes = sorted(routes, key=get_route_sort_key)
        assert sorted_routes[0].path_format == '/specific'
        assert sorted_routes[1].path_format == '/{param}'

    def test_longer_paths_before_shorter(self) -> None:
        routes = [
            create_mock_route('/short'),
            create_mock_route('/longer/path'),
        ]
        sorted_routes = sorted(routes, key=get_route_sort_key)
        assert sorted_routes[0].path_format == '/longer/path'
        assert sorted_routes[1].path_format == '/short'

    def test_param_position_matters(self) -> None:
        routes = [
            create_mock_route('/{param}/detail'),
            create_mock_route('/static/{param}'),
        ]
        sorted_routes = sorted(routes, key=get_route_sort_key)
        assert sorted_routes[0].path_format == '/static/{param}'
        assert sorted_routes[1].path_format == '/{param}/detail'

    def test_complex_case(self) -> None:
        routes = [
            create_mock_route('/{param}'),
            create_mock_route('/admin/addservice'),
            create_mock_route('/admin/{action}'),
            create_mock_route('/short'),
        ]
        expected_order = [
            '/admin/addservice',  # Exact + longer
            '/short',  # Exact but shorter
            '/admin/{action}',  # Param, same length as above but param
            '/{param}',  # Param + shortest
        ]
        sorted_routes = sorted(routes, key=get_route_sort_key)
        assert [r.path_format for r in sorted_routes] == expected_order

    def test_path_parameters_with_suffix(self) -> None:
        routes = [
            create_mock_route('/{param}.mvc'),
            create_mock_route('/static.mvc'),
        ]
        sorted_routes = sorted(routes, key=get_route_sort_key)
        assert sorted_routes[0].path_format == '/static.mvc'
        assert sorted_routes[1].path_format == '/{param}.mvc'
