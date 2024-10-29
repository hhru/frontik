import importlib
import logging
import pkgutil
import re
from collections.abc import Generator
from pathlib import Path
from typing import Any, MutableSequence, Optional, Union

from fastapi import APIRouter
from fastapi.routing import APIRoute
from starlette.routing import Match

routing_logger = logging.getLogger('frontik.routing')

routers: list[APIRouter] = []
_regex_mapping: list[tuple[re.Pattern, APIRoute]] = []
_fastapi_routes: list[APIRoute] = []


class FrontikRegexRouter(APIRouter):
    def add_api_route(self, *args: Any, **kwargs: Any) -> None:
        super().add_api_route(*args, **kwargs)
        route: APIRoute = self.routes[-1]  # type: ignore
        _regex_mapping.append((re.compile(route.path), route))


class FastAPIRouter(APIRouter):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        routers.append(self)

    async def __call__(self, scope, receive, send):
        assert scope['type'] == 'http'

        if 'router' not in scope:
            scope['router'] = self

        route = scope['route']
        await route.handle(scope, receive, send)

    def add_api_route(self, *args: Any, **kwargs: Any) -> None:
        super().add_api_route(*args, **kwargs)
        _fastapi_routes.append(self.routes[-1])  # type: ignore

    def add_route(self, *args: Any, **kwargs: Any) -> None:
        super().add_route(*args, **kwargs)
        _fastapi_routes.append(self.routes[-1])  # type: ignore


def _iter_submodules(path: MutableSequence[str], prefix: str = '') -> Generator:
    """Find packages recursively, including PEP420 packages"""
    yield from pkgutil.walk_packages(path, prefix)
    namespace_packages: dict = {}
    for path_root in path:
        for sub_path in Path(path_root).iterdir():
            if str(sub_path).endswith('__pycache__'):
                continue
            if sub_path.is_dir():
                ns_paths = namespace_packages.setdefault(prefix + sub_path.name, [])
                ns_paths.append(str(sub_path))
    for name, paths in namespace_packages.items():
        yield pkgutil.ModuleInfo(None, name, True)  # type: ignore
        yield from _iter_submodules(paths, name + '.')


def import_all_pages(app_module: str) -> None:
    """Import all pages on startup"""

    try:
        pages_package = importlib.import_module(f'{app_module}.pages')
    except ModuleNotFoundError:
        routing_logger.warning('There is no pages module')
        return

    for _, name, __ in _iter_submodules(pages_package.__path__):
        full_name = pages_package.__name__ + '.' + name
        try:
            importlib.import_module(full_name)
        except ModuleNotFoundError:
            continue
        except Exception as ex:
            raise RuntimeError('failed on import page %s %s', full_name, ex)


router = FastAPIRouter()
regex_router = FrontikRegexRouter()
not_found_router = APIRouter()
method_not_allowed_router = APIRouter()


def _find_fastapi_route(scope: dict) -> Optional[APIRoute]:
    for route in _fastapi_routes:
        match, child_scope = route.matches(scope)
        if match == Match.FULL:
            scope.update(child_scope)
            scope['route'] = route
            return route

    route_path = scope['path']
    if route_path != '/':
        if route_path.endswith('/'):
            scope['path'] = scope['path'].rstrip('/')
        else:
            scope['path'] = scope['path'] + '/'

    for route in _fastapi_routes:
        match, child_scope = route.matches(scope)
        if match == Match.FULL:
            scope.update(child_scope)
            scope['route'] = route
            return route

    return None


def _find_regex_route(path: str, method: str) -> Union[tuple[APIRoute, dict], tuple[None, dict]]:
    for pattern, route in _regex_mapping:
        match = pattern.match(path)
        if match and next(iter(route.methods), None) == method:
            return route, match.groupdict()

    return None, {}


def find_route(path: str, method: str) -> dict:
    route: APIRoute
    route, path_params = _find_regex_route(path, method)  # type: ignore
    scope = {
        'type': 'http',
        'path': path,
        'method': method,
        'route': route,
        'path_params': path_params,
    }

    if route is None:
        route = _find_fastapi_route(scope)

    if route is None and method == 'HEAD':
        scope = find_route(path, 'GET')
        route = scope['route']

    if route is None:
        routing_logger.error('match for request url %s "%s" not found', method, path)

        allowed_methods = get_allowed_methods(scope)
        if len(allowed_methods) > 0:
            scope['allowed_methods'] = allowed_methods
            route = method_not_allowed_router.routes[-1]
        else:
            route = not_found_router.routes[-1]

        scope['route'] = route

    scope['method'] = next(iter(route.methods))
    scope['endpoint'] = route.endpoint
    return scope


def get_allowed_methods(scope: dict) -> list[str]:
    path: str = scope.get('path')  # type: ignore
    allowed_methods = []
    for method in ('GET', 'POST', 'PUT', 'DELETE', 'HEAD'):
        scope['method'] = method
        route = _find_fastapi_route(scope)
        if route is None:
            route, _ = _find_regex_route(path, method)

        if route is not None:
            allowed_methods.append(method)

    return allowed_methods
