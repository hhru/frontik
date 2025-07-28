from __future__ import annotations

import importlib
import json
import logging
import os
import pathlib
from typing import TYPE_CHECKING, Callable, TypedDict

from fastapi import APIRouter

from frontik.routing import (
    _fastapi_routes,
    find_route,
    get_route_sort_key,
    import_all_pages,
    not_found_router,
)

if TYPE_CHECKING:
    from starlette.routing import BaseRoute

routing_logger = logging.getLogger('frontik.routing')

DELIMITER = ','
SRC_FOLDER = '/source-site-packages/'
ROUTES_MAP_MODULE_NAME = 'routes_map_exclude-dev-watcher_'
ROUTES_MAP_PATH = f'/{SRC_FOLDER}/frontik/{ROUTES_MAP_MODULE_NAME}.py'
MAX_CHANGED_FILES_COUNT_TO_INVALIDATE = 15
EMPTY_FS_PATH = 'empty'

SRC_FOLDER_LEN = len(SRC_FOLDER)


def make_route_endpoint(endpoint: str) -> Callable[[], str]:
    def route_endpoint() -> str:
        return endpoint

    return route_endpoint


def get_diff_cache_and_fs(
    routes_map: list[RouteCache],
    py_files_mtime: list[PageMtime],
    exclude_pages_to_add: list[PageMtime],
) -> DiffResult:
    routes_cache_set = set()
    routes_cache_endpoint_map_mtime: dict[str, float] = {}
    for route_cache in routes_map:
        endpoint = route_cache['endpoint']
        mtime = route_cache['mtime']
        fs_path = route_cache['fs_path']
        routes_cache_endpoint_map_mtime[endpoint] = mtime
        routes_cache_set.add((endpoint, fs_path))

    py_files_mtime_set = set()
    py_files_endpoint_map_mtime: dict[str, float] = {}

    for page_file in py_files_mtime:
        endpoint = page_file['endpoint']
        mtime = page_file['mtime']
        fs_path = page_file['fs_path']
        py_files_endpoint_map_mtime[endpoint] = mtime
        py_files_mtime_set.add((endpoint, fs_path))

    exclude_pages_mtime_set = {(rc['endpoint'], rc['fs_path']) for rc in exclude_pages_to_add}

    only_in_route_cache = routes_cache_set - py_files_mtime_set
    only_in_py_files_mtime = py_files_mtime_set - routes_cache_set - exclude_pages_mtime_set

    need_delete: dict[str, PageMtime] = {}
    need_add: dict[str, PageMtime] = {}

    for endpoint, fs_path in only_in_route_cache:
        if fs_path != EMPTY_FS_PATH:
            need_delete[endpoint] = {
                'endpoint': endpoint,
                'fs_path': fs_path,
                'mtime': routes_cache_endpoint_map_mtime[endpoint],
            }

    for endpoint, fs_path in only_in_py_files_mtime:
        if fs_path != EMPTY_FS_PATH:
            need_add[endpoint] = {
                'endpoint': endpoint,
                'fs_path': fs_path,
                'mtime': py_files_endpoint_map_mtime[endpoint],
            }

    return {
        'need_delete': need_delete,
        'need_add': need_add,
    }


class RouteCache(TypedDict):
    endpoint: str
    method: str
    path: str
    mtime: float
    fs_path: str


class PageMtime(TypedDict):
    endpoint: str
    mtime: float
    fs_path: str


class DiffResult(TypedDict):
    need_add: dict[str, PageMtime]
    need_delete: dict[str, PageMtime]


def fs_path_to_entry(fs_path: str) -> str:
    return fs_path[SRC_FOLDER_LEN:].replace('/__init__.py', '').replace('.py', '').replace('/', '.')


def map_py_files_mtime(root_folder: str) -> dict[str, PageMtime]:
    py_files_mtime: dict[str, PageMtime] = {}
    for dirpath, _, filenames in os.walk(root_folder):
        for filename in filenames:
            if filename.endswith('.py') and '.null-ls_' not in filename:
                full_path = str(pathlib.Path(dirpath) / filename)
                mtime = pathlib.Path(full_path).stat().st_mtime
                endpoint = fs_path_to_entry(full_path)
                py_files_mtime[endpoint] = {
                    'mtime': mtime,
                    'fs_path': full_path,
                    'endpoint': endpoint,
                }
    return py_files_mtime


def delete_empty_modules(pages: list[PageMtime]) -> list[PageMtime]:
    return [page for page in pages if page.get('fs_path') != EMPTY_FS_PATH]


def convert_fastapi_route_to_cache(route: BaseRoute, fs_path: str, mtime: float) -> RouteCache:
    module_name = route.endpoint.__module__  # type: ignore[attr-defined]
    method = next(iter(route.methods), 'GET').upper()  # type: ignore[attr-defined]
    path = route.path  # type: ignore[attr-defined]

    return {
        'endpoint': module_name,
        'method': method,
        'path': path,
        'mtime': mtime,
        'fs_path': fs_path,
    }


class DevRouteManager:
    def __init__(self) -> None:
        self.routes_map_module: dict[str, RouteCache] = {}
        self.exclude_pages_to_add: list[PageMtime] = []
        self.fake_routes: list[BaseRoute] = []
        self.fake_dev_router = APIRouter()
        self.py_files_mtime: dict[str, PageMtime] = {}
        self.fastapi_routes: list[BaseRoute] = _fastapi_routes
        self.not_found_router: APIRouter = not_found_router

    def import_all_pages(self, app_module: str) -> None:
        pages_root_folder = str(pathlib.Path(SRC_FOLDER) / app_module / 'pages')
        self.py_files_mtime = map_py_files_mtime(pages_root_folder)

        if pathlib.Path(ROUTES_MAP_PATH).is_file():
            routing_logger.info('Importing routes_map module')

            module = importlib.import_module(f'frontik.{ROUTES_MAP_MODULE_NAME}')
            routes_map = module.routes_map
            self.exclude_pages_to_add = module.exclude_pages_to_add
            mandatory_for_import = module.mandatory_for_import

            for route_data in mandatory_for_import:
                importlib.import_module(route_data['endpoint'])

            diff_cache_and_fs_result = get_diff_cache_and_fs(
                routes_map,
                list(self.py_files_mtime.values()),
                self.exclude_pages_to_add,
            )

            need_add = diff_cache_and_fs_result['need_add']
            need_delete = diff_cache_and_fs_result['need_delete']
            need_to_update = []

            for route_data in routes_map:
                endpoint = route_data['endpoint']
                mtime = route_data['mtime']
                if endpoint in self.py_files_mtime and self.py_files_mtime[endpoint]['mtime'] != mtime:
                    need_to_update.append(route_data)
                elif endpoint not in need_delete:
                    self.add_fake_route(route_data)

            routes_add_to_cache = list(need_add.values()) + need_to_update
            routing_logger.info('Routes to delete: %s', len(diff_cache_and_fs_result['need_delete']))
            routing_logger.info('Routes to add: %s', len(routes_add_to_cache))

            if routes_add_to_cache:
                if len(routes_add_to_cache) > MAX_CHANGED_FILES_COUNT_TO_INVALIDATE:
                    self.create_route_map_module(app_module)
                    return
                self.add_routes_to_cache(routes_add_to_cache)

            self.fake_routes.sort(key=get_route_sort_key)
            self.fastapi_routes.sort(key=get_route_sort_key)
            self.update_file_cache()
        else:
            self.create_route_map_module(app_module)

    def create_route_map_module(self, app_module: str) -> None:
        routing_logger.info('Routes map file not found, creating: %s', ROUTES_MAP_PATH)
        import_all_pages(app_module)

        self.proccess_fastapi_routes_to_dev_route(self.py_files_mtime)

        diff_cache_and_fs_result = get_diff_cache_and_fs(
            list(self.routes_map_module.values()),
            list(self.py_files_mtime.values()),
            [],
        )
        self.exclude_pages_to_add = list(diff_cache_and_fs_result['need_add'].values())
        self.update_file_cache()

    def proccess_fastapi_routes_to_dev_route(self, module_path_map: dict[str, PageMtime]) -> list[RouteCache]:
        routes_data: list[RouteCache] = []
        routing_logger.info('run convert_fastapi_routes_to_cache')

        for route in self.fastapi_routes:
            module_name = getattr(route.endpoint, '__module__', '')  # type: ignore[attr-defined]
            fs_data: PageMtime = module_path_map.get(
                module_name, {'fs_path': EMPTY_FS_PATH, 'mtime': 0, 'endpoint': ''}
            )
            route_entry = convert_fastapi_route_to_cache(route, fs_data['fs_path'], fs_data['mtime'])

            self.add_fake_route(route_entry)
            routes_data.append(route_entry)

        return routes_data

    def add_fake_route(self, route_data: RouteCache) -> None:
        path = route_data['path']
        method = route_data['method'].upper()
        endpoint = route_data['endpoint']
        route_key = f'{method}.{path}'
        self.routes_map_module.update({route_key: route_data})

        routing_logger.info('Adding fake route, path: %s, method: %s', path, method)
        route_endpoint = make_route_endpoint(endpoint)

        self.fake_dev_router.add_api_route(f'/fake{path}', route_endpoint, methods=[method])
        self.fake_routes.append(self.fake_dev_router.routes[-1])

    def add_routes_to_cache(self, py_files_mtime: list[PageMtime]) -> None:
        for route in py_files_mtime:
            endpoint = route['endpoint']
            importlib.import_module(endpoint)
            routing_logger.info('Add route to cache: %s, , mtime: %s', endpoint, route['mtime'])

        self.proccess_fastapi_routes_to_dev_route(self.py_files_mtime)

    def update_file_cache(self) -> None:
        with pathlib.Path(ROUTES_MAP_PATH).open('w', encoding='utf-8') as file:
            file.write(f'routes_map = {json.dumps(list(self.routes_map_module.values()))}\n')
            file.write(f'exclude_pages_to_add = {json.dumps(self.exclude_pages_to_add)}\n')
            mandatory_for_import = [convert_fastapi_route_to_cache(self.not_found_router.routes[-1], EMPTY_FS_PATH, 0)]
            file.write(f'mandatory_for_import = {json.dumps(mandatory_for_import)}\n')

    def import_route(self, path: str, method: str) -> None:
        scope = find_route(path, method.upper(), self.fake_routes, '/fake')

        if scope and 'endpoint' in scope and scope['endpoint'].__name__ == 'route_endpoint':
            endpoint_module_name = scope['endpoint']()
            importlib.import_module(endpoint_module_name)
            routing_logger.info('Importing module for matched route: %s', endpoint_module_name)

        self.fastapi_routes.sort(key=get_route_sort_key)
