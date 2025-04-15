import importlib
import importlib.util
import logging
import pkgutil
import re
from collections.abc import Generator
from pathlib import Path
from typing import Any, MutableSequence, Optional, Union

from fastapi import APIRouter
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute, Match

routing_logger = logging.getLogger('frontik.routing')

routers: list[APIRouter] = []
_regex_mapping: list[tuple[re.Pattern, APIRoute]] = []
_fastapi_routes: list[BaseRoute] = []


def get_route_sort_key(route: BaseRoute) -> tuple:
    if not isinstance(route, APIRoute):
        return -500, None

    segments = [s for s in route.path_format.split('/') if s]
    param_flags = tuple((s.startswith('{') and s.endswith('}')) for s in segments)
    if sum(param_flags) == 0:  # keep exact urls on first places
        return -500, None
    return -len(segments), param_flags


class FrontikRouter(APIRouter):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        routers.append(self)

    async def app(self, scope, receive, send):
        assert scope['type'] == 'http'

        if 'router' not in scope:
            scope['router'] = self

        route = scope['route']
        await route.handle(scope, receive, send)

    def add_api_route(self, path: str, *args: Any, **kwargs: Any) -> None:
        if path.endswith('/') and path != '/':
            path = path.rstrip('/')
        super().add_api_route(path, *args, **kwargs)
        _fastapi_routes.append(self.routes[-1])

    def add_route(self, path: str, *args: Any, **kwargs: Any) -> None:
        if path.endswith('/') and path != '/':
            path = path.rstrip('/')
        super().add_api_route(path, *args, **kwargs)
        _fastapi_routes.append(self.routes[-1])

    def mount(self, path: str, *args: Any, **kwargs: Any) -> None:
        super().mount(path, *args, **kwargs)
        _fastapi_routes.append(self.routes[-1])


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

    _spec = importlib.util.find_spec(f'{app_module}.pages')
    if _spec is None:
        routing_logger.warning('There is no pages module')
        return

    pages_package_path = f'{app_module}.pages'
    pages_package = importlib.import_module(pages_package_path)

    for _, name, __ in _iter_submodules(pages_package.__path__, f'{pages_package_path}.'):
        _spec = importlib.util.find_spec(name)
        if _spec is None:
            continue

        importlib.import_module(name)

    _fastapi_routes.sort(key=get_route_sort_key)


router = FrontikRouter()
not_found_router = APIRouter()
method_not_allowed_router = APIRouter()


def _find_fastapi_route_partial(scope: dict) -> set[str]:
    result = set()

    for route in _fastapi_routes:
        if isinstance(route, APIRoute) and 'OPTIONS' in route.methods:
            continue
        match, child_scope = route.matches(scope)
        if isinstance(route, APIRoute) and match == Match.PARTIAL:
            result.update(route.methods)

    return result


def _find_fastapi_route_exact(scope: dict) -> Optional[BaseRoute]:
    for route in _fastapi_routes:
        if isinstance(route, APIRoute) and scope['method'] not in route.methods:
            continue
        match, child_scope = route.matches(scope)
        if match == Match.FULL:
            scope.update(child_scope)
            scope['route'] = route
            return route

    return None


def _find_regex_route(path: str, method: str) -> Union[tuple[BaseRoute, dict], tuple[None, dict]]:
    for pattern, route in _regex_mapping:
        match = pattern.match(path)
        if match and method in route.methods:
            return route, match.groupdict()

    return None, {}


def find_route(path: str, method: str) -> dict:
    route, path_params = _find_regex_route(path, method)

    if path.endswith('/') and path != '/':
        path = path.rstrip('/')

    scope: dict[str, Any] = {
        'type': 'http',
        'path': path,
        'method': method,
        'route': route,
        'path_params': path_params,
    }

    if route is None:
        route = _find_fastapi_route_exact(scope)

    if route is None and method == 'HEAD':
        scope = find_route(path, 'GET')
        scope['method'] = 'HEAD'
        route = scope['route']
        if route is not None and isinstance(route, APIRoute):
            route.methods.add('HEAD')

    if route is None:
        allowed_methods = get_allowed_methods(scope)
        if len(allowed_methods) > 0:
            scope['allowed_methods'] = allowed_methods
            route = method_not_allowed_router.routes[-1]
        else:
            route = not_found_router.routes[-1]

        if isinstance(route, APIRoute) and method not in route.methods:
            route.methods.add(method)

        routing_logger.error(
            'match for request url %s "%s" not found, using %s',
            method,
            path,
            route.endpoint.__module__ + '.' + route.endpoint.__name__,
        )
        scope['route'] = route

    if isinstance(route, APIRoute):
        scope['endpoint'] = route.endpoint
    return scope


def get_allowed_methods(scope: dict) -> list[str]:
    return list(_find_fastapi_route_partial(scope))
