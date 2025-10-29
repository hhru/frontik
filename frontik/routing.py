from __future__ import annotations

import importlib
import importlib.util
import logging
import pkgutil
from collections.abc import Generator, MutableSequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute, Match

if TYPE_CHECKING:
    from collections.abc import Generator, MutableSequence


routing_logger = logging.getLogger('frontik.routing')

routers: list[APIRouter] = []
_fastapi_routes: list[BaseRoute] = []


def is_param_segment(segment: str) -> bool:
    return '{' in segment


def get_route_sort_key(route: BaseRoute) -> tuple:
    if not isinstance(route, APIRoute):
        return 3, 0, ()  # Non-APIRoute last (3)

    segments = [s for s in route.path_format.split('/') if s]
    has_params = any(is_param_segment(s) for s in segments)

    if not has_params:
        # Exact routes first (1), sorted by segment count (longer first)
        return 1, -len(segments), ()
    else:
        # Routes with params come after exact routes (2), sorted by:
        # 1. By segment count (longer first)
        # 2. Position of params (later params = higher priority)
        param_flags = tuple(is_param_segment(s) for s in segments)
        return 2, -len(segments), param_flags


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
preflight_router = APIRouter()


def _find_fastapi_route_partial(scope: dict) -> set[str]:
    result = set()

    for route in _fastapi_routes:
        if isinstance(route, APIRoute) and 'OPTIONS' in route.methods:
            continue
        match, child_scope = route.matches(scope)
        if isinstance(route, APIRoute) and match == Match.PARTIAL:
            result.update(route.methods)

    return result


def _find_fastapi_route_exact(scope: dict[str, Any], fastapi_routes: list[BaseRoute]) -> BaseRoute | None:
    for route in fastapi_routes:
        if isinstance(route, APIRoute) and scope['method'] not in route.methods:
            continue
        match, child_scope = route.matches(scope)

        if match == Match.FULL:
            scope.update(child_scope)
            scope['route'] = route
            return route

    return None


def find_route(
    path: str, method: str, fastapi_routes: list[BaseRoute] | None = None, prefix: str = ''
) -> dict[str, Any]:
    if path.endswith('/') and path != '/':
        path = path.rstrip('/')

    scope: dict[str, Any] = {
        'type': 'http',
        'path': f'{prefix}{path}',
        'method': method.upper(),
        'route': None,
    }

    route = _find_fastapi_route_exact(scope, fastapi_routes if fastapi_routes is not None else _fastapi_routes)

    if fastapi_routes is not None:
        route = _find_fastapi_route_exact(scope, fastapi_routes)

    if route is None and method == 'HEAD':
        scope = find_route(path, 'GET', fastapi_routes)
        scope['method'] = 'HEAD'
        route = scope['route']
        if route is not None and isinstance(route, APIRoute):
            route.methods.add('HEAD')

    if route is None and method == 'OPTIONS':
        route = preflight_router.routes[-1]
        if isinstance(route, APIRoute):
            route.methods.add(method)
        scope['route'] = route

    if route is None:
        allowed_methods = get_allowed_methods(scope)
        if len(allowed_methods) > 0:
            scope['allowed_methods'] = allowed_methods
            route = method_not_allowed_router.routes[-1]
        else:
            route = not_found_router.routes[-1]

        if isinstance(route, APIRoute) and method not in route.methods:
            route.methods.add(method)

        assert isinstance(route, APIRoute)
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
