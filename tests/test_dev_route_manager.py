from __future__ import annotations

import importlib
import pathlib
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import APIRouter

from frontik import dev_route_manager
from frontik.routing import get_route_sort_key
from tests.instances import frontik_test_app_with_dev_router

routing = dev_route_manager


def test_make_route_endpoint_returns_callable() -> None:
    endpoint = 'some.endpoint'
    fn = routing.make_route_endpoint(endpoint)
    assert callable(fn)
    assert fn() == endpoint


def test_get_diff_cache_and_fs_basic() -> None:
    routes_map: list[dev_route_manager.RouteCache] = [
        {'endpoint': 'a', 'method': 'GET', 'path': '/a', 'mtime': 10, 'fs_path': 'path1'},
        {'endpoint': 'b', 'method': 'GET', 'path': '/b', 'mtime': 20, 'fs_path': routing.EMPTY_FS_PATH},
        {'endpoint': 'c', 'method': 'GET', 'path': '/c', 'mtime': 30, 'fs_path': 'path3'},
    ]
    py_files_mtime: list[dev_route_manager.PageMtime] = [
        {'endpoint': 'a', 'mtime': 10, 'fs_path': 'path1'},
        {'endpoint': 'd', 'mtime': 40, 'fs_path': 'path4'},
    ]
    exclude_pages_to_add: list[dev_route_manager.PageMtime] = [{'endpoint': 'd', 'mtime': 40, 'fs_path': 'path4'}]

    diff = routing.get_diff_cache_and_fs(routes_map, py_files_mtime, exclude_pages_to_add)

    # 'b' should be detected as need_delete = it has EMPTY_FS_PATH => excluded
    # 'c' only in route cache with non-empty fs path -> need_delete
    # 'd' only in py_files_mtime but is in exclude_pages_to_add -> no need_add
    assert 'b' not in diff['need_delete']
    assert 'c' in diff['need_delete']
    assert 'd' not in diff['need_add']
    assert 'a' not in diff['need_delete']
    assert 'a' not in diff['need_add']


def test_fs_path_to_entry() -> None:
    base_path = routing.SRC_FOLDER + 'mypkg/mymodule.py'
    src_folder_len = len(routing.SRC_FOLDER)
    assert routing.fs_path_to_entry(base_path, src_folder_len) == 'mypkg.mymodule'

    path_with_init = routing.SRC_FOLDER + 'pkg/__init__.py'
    assert routing.fs_path_to_entry(path_with_init, src_folder_len) == 'pkg'

    nested_path = routing.SRC_FOLDER + 'a/b/c.py'
    assert routing.fs_path_to_entry(nested_path, src_folder_len) == 'a.b.c'


@patch('os.walk')
@patch('pathlib.Path.stat')
def test_map_py_files_mtime_os_walk_and_stat(mock_stat: Mock, mock_walk: Mock) -> None:
    base_folder = '/source-site-packages/app/pages'

    mock_walk.return_value = [
        (base_folder, [], ['file1.py', 'file2.null-ls_', 'file3.py']),
        (base_folder + '/sub', [], ['subfile.py']),
    ]

    def stat_side_effect() -> Mock:
        mock = Mock()
        mock.st_mtime = 123.456
        return mock

    mock_stat.side_effect = stat_side_effect
    results = routing.map_py_files_mtime(base_folder, len(routing.SRC_FOLDER))

    assert any('file1' in k or 'file3' in k or 'subfile' in k for k in results)
    assert all(v['mtime'] == 123.456 for v in results.values())


def test_convert_fastapi_route_to_cache_minimal() -> None:
    route = MagicMock()
    route.endpoint.__module__ = 'mod'
    route.methods = {'post'}
    route.path = '/path'

    result = routing.convert_fastapi_route_to_cache(route, '/some/fs', 123)
    assert result['endpoint'] == 'mod'
    assert result['mtime'] == 123
    assert result['fs_path'] == '/some/fs'
    assert result['method'] == 'POST'
    assert result['path'] == '/path'


@pytest.fixture
def dummy_route() -> MagicMock:
    mock_route = MagicMock()
    mock_route.endpoint.__module__ = 'dummy.module'
    mock_route.methods = {'GET'}
    mock_route.path = '/dummy'
    return mock_route


@pytest.fixture
def dev_rm() -> dev_route_manager.DevRouteManager:
    route_manager = routing.DevRouteManager()
    route_manager.fake_routes.clear()
    route_manager.fake_dev_router = APIRouter()
    route_manager.update_file_cache = MagicMock()  # type: ignore[method-assign]
    return route_manager


@patch('importlib.import_module')
@patch('frontik.dev_route_manager.map_py_files_mtime')
@patch('frontik.dev_route_manager.get_diff_cache_and_fs')
@patch('pathlib.Path.is_file')
def test_import_all_pages_with_routes_map(
    mock_is_file: Mock,
    mock_diff: Mock,
    mock_map_py_files: Mock,
    mock_import_module: Mock,
    dummy_route: MagicMock,
    dev_rm: dev_route_manager.DevRouteManager,
) -> None:
    mock_is_file.return_value = True

    routes_map = [
        {'endpoint': 'ep1', 'method': 'GET', 'path': '/p1', 'mtime': 1, 'fs_path': '/f1'},
        {'endpoint': 'ep2', 'method': 'POST', 'path': '/p2', 'mtime': 2, 'fs_path': '/f2'},
    ]
    exclude_pages_to_add = [{'endpoint': 'ep3', 'mtime': 3, 'fs_path': '/f3'}]
    mandatory_for_import = [{'endpoint': 'must.import'}]

    module_mock = MagicMock()
    module_mock.routes_map = routes_map
    module_mock.exclude_pages_to_add = exclude_pages_to_add
    module_mock.mandatory_for_import = mandatory_for_import

    def import_module_side_effect(name: str) -> MagicMock:
        if name == f'frontik.{routing.ROUTES_MAP_MODULE_NAME}':
            return module_mock
        else:
            return MagicMock()

    mock_import_module.side_effect = import_module_side_effect

    mock_map_py_files.return_value = {r['endpoint']: r for r in routes_map}
    mock_diff.return_value = {'need_add': {}, 'need_delete': {}}
    dev_rm.fastapi_routes = [dummy_route]

    dev_rm.import_all_pages('app')

    mock_import_module.assert_any_call('must.import')
    assert len(dev_rm.fake_routes) > 0
    assert dev_rm.fake_routes == sorted(dev_rm.fake_routes, key=get_route_sort_key)
    assert dev_rm.fastapi_routes == sorted(dev_rm.fastapi_routes, key=get_route_sort_key)


@patch('pathlib.Path.is_file')
@patch('frontik.dev_route_manager.import_all_pages')
def test_import_all_pages_without_routes_map(
    mock_import_all_pages: MagicMock, mock_is_file: MagicMock, dev_rm: dev_route_manager.DevRouteManager
) -> None:
    mock_is_file.return_value = False
    dev_rm.import_all_pages('app')
    mock_import_all_pages.assert_called_once_with('app')


@patch('importlib.import_module')
def test_add_routes_to_cache_imports_and_process(
    mock_import_module: MagicMock, dev_rm: dev_route_manager.DevRouteManager
) -> None:
    proccess_mock = patch.object(dev_rm, 'proccess_fastapi_routes_to_dev_route', return_value=[]).start()
    pages: list[dev_route_manager.PageMtime] = [{'endpoint': 'mod1', 'mtime': 1.1, 'fs_path': '/fs1'}]

    dev_rm.add_routes_to_cache(pages)

    mock_import_module.assert_called_with('mod1')
    proccess_mock.assert_called_with(dev_rm.py_files_mtime)
    proccess_mock.stop()


def test_add_fake_route_adds_route_and_updates_map(dev_rm: dev_route_manager.DevRouteManager) -> None:
    route_data: dev_route_manager.RouteCache = {
        'endpoint': 'myendpoint',
        'method': 'post',
        'path': '/path',
        'mtime': 3,
        'fs_path': '/fs',
    }
    starting_count = len(dev_rm.fake_routes)
    dev_rm.add_fake_route(route_data)
    key = f'{route_data["method"].upper()}.{route_data["path"]}'
    assert key in dev_rm.routes_map_module
    assert len(dev_rm.fake_routes) == starting_count + 1
    assert any(route.path == '/fake/path' for route in dev_rm.fake_dev_router.routes)  # type: ignore[attr-defined]


@patch('importlib.import_module')
@patch('frontik.dev_route_manager.find_route')
def test_import_route_calls_import_module_if_match(
    mock_find_route: MagicMock, mock_import_module: MagicMock, dev_rm: dev_route_manager.DevRouteManager
) -> None:
    mock_endpoint = MagicMock()
    mock_endpoint.__name__ = 'route_endpoint'
    mock_endpoint.side_effect = lambda: 'some.endpoint'

    mock_scope = {'endpoint': mock_endpoint}
    mock_find_route.return_value = mock_scope

    dev_rm.fake_routes = [mock_scope]  # type: ignore[list-item]
    dev_rm.import_route('/path', 'get')

    mock_import_module.assert_called_with('some.endpoint')


def test_import_route_no_import_if_no_match(dev_rm: dev_route_manager.DevRouteManager) -> None:
    with patch('frontik.dev_route_manager.find_route', return_value=None):
        dev_rm.fake_routes = []
        with patch('importlib.import_module') as mock_import_module:
            dev_rm.import_route('/no-route', 'GET')
            mock_import_module.assert_not_called()


def make_mock_route(module_name: str, methods: set[str] | None = None, path: str = '/') -> MagicMock:
    route_mock = MagicMock()
    route_mock.endpoint.__module__ = module_name
    route_mock.methods = methods or {'GET'}
    route_mock.path = path
    return route_mock


def test_proccess_fastapi_routes_to_dev_route_adds_fake_routes(dev_rm: dev_route_manager.DevRouteManager) -> None:
    route_get = make_mock_route('mod1', {'GET'}, '/p1')
    route_post = make_mock_route('mod2', {'POST'}, '/p2')
    dev_rm.fastapi_routes = [route_get, route_post]

    module_path_map: dict[str, dev_route_manager.PageMtime] = {
        'mod1': {'endpoint': 'mod1', 'fs_path': '/fs1', 'mtime': 100},
        'mod2': {'endpoint': 'mod2', 'fs_path': '/fs2', 'mtime': 200},
    }
    output = dev_rm.proccess_fastapi_routes_to_dev_route(module_path_map)

    assert len(output) == 2
    assert len(dev_rm.fake_routes) >= 2
    rcache = output[0]

    assert 'endpoint' in rcache
    assert 'mtime' in rcache
    assert 'fs_path' in rcache
    assert 'method' in rcache
    assert 'path' in rcache


ROUTE_MAP_PATH = f'frontik/{routing.ROUTES_MAP_MODULE_NAME}.py'


class TestDevRouteManager:
    def clear_autogenerated(self) -> None:
        if pathlib.Path(ROUTE_MAP_PATH).is_file():
            pathlib.Path(ROUTE_MAP_PATH).unlink()

    def setup_method(self) -> None:
        self.clear_autogenerated()
        frontik_test_app_with_dev_router.start()
        frontik_test_app_with_dev_router.stop()
        frontik_test_app_with_dev_router.start()

    def teardown_method(self) -> None:
        self.clear_autogenerated()
        frontik_test_app_with_dev_router.stop()

    def test_get_on_demand_page(self) -> None:
        result = frontik_test_app_with_dev_router.get_page('/index')
        assert result.status_code == 200
        assert result.content == b'{"ok":200}'

    def test_generate_routes_map_file(self) -> None:
        module = importlib.import_module(f'frontik.{routing.ROUTES_MAP_MODULE_NAME}')
        routes_map = module.routes_map
        mandatory_for_import = module.mandatory_for_import
        exclude_pages_to_add = module.exclude_pages_to_add

        first_mandatory = mandatory_for_import[0]
        assert first_mandatory['endpoint'] == 'frontik.app'
        assert first_mandatory['method'] == 'GET'
        assert first_mandatory['path'] == '__not_found'

        index_route = next((route for route in routes_map if route['path'] == '/index'), None)
        assert index_route is not None
        assert index_route['endpoint'] == 'tests.projects.test_app.pages.index'
        assert index_route['method'] == 'GET'
        assert index_route['path'] == '/index'

        assert len(exclude_pages_to_add) == 0
