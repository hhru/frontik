from __future__ import annotations

import importlib
import logging
import pkgutil
import re
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, MutableSequence, Optional, Type, Union

from fastapi import APIRouter
from fastapi.routing import APIRoute
from starlette.routing import Match

if TYPE_CHECKING:
    from frontik.handler import PageHandler

routing_logger = logging.getLogger('frontik.routing')

routers: list[APIRouter] = []
_plain_routes: dict[tuple[str, str], tuple[APIRoute, type[PageHandler] | None]] = {}
_regex_mapping: list[tuple[re.Pattern, APIRoute, Type[PageHandler]]] = []
_fastapi_routes: list[APIRoute] = []


class FrontikRouter(APIRouter):
    def __init__(self, *, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        routers.append(self)
        self._cls: Optional[Type[PageHandler]] = None
        self._base_cls: Optional[Type[PageHandler]] = cls

    def get(self, path: str, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> Callable:
        self._cls = self._base_cls or cls
        return super().get(path, **kwargs)

    def post(self, path: str, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> Callable:
        self._cls = self._base_cls or cls
        return super().post(path, **kwargs)

    def put(self, path: str, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> Callable:
        self._cls = self._base_cls or cls
        return super().put(path, **kwargs)

    def delete(self, path: str, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> Callable:
        self._cls = self._base_cls or cls
        return super().delete(path, **kwargs)

    def head(self, path: str, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> Callable:
        self._cls = self._base_cls or cls
        return super().head(path, **kwargs)

    def options(self, path: str, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> Callable:
        self._cls = self._base_cls or cls
        return super().options(path, **kwargs)

    def add_api_route(self, *args: Any, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> None:
        super().add_api_route(*args, **kwargs)
        self._cls = self._base_cls or cls or self._cls
        route: APIRoute = self.routes[-1]  # type: ignore
        method = next(iter(route.methods), None)
        assert method is not None
        path = route.path.strip('/')

        if _plain_routes.get((path, method), None) is not None:
            raise RuntimeError(f'route for {method} {path} already exists')

        _plain_routes[(path, method)] = (route, self._cls)  # we need our routing, for getting route object


class FrontikRegexRouter(APIRouter):
    def __init__(self, *, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        routers.append(self)
        self._cls: Optional[Type[PageHandler]] = None
        self._base_cls: Optional[Type[PageHandler]] = cls

    def get(self, path: str, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> Callable:
        self._cls = self._base_cls or cls
        return super().get(path, **kwargs)

    def post(self, path: str, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> Callable:
        self._cls = self._base_cls or cls
        return super().post(path, **kwargs)

    def put(self, path: str, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> Callable:
        self._cls = self._base_cls or cls
        return super().put(path, **kwargs)

    def delete(self, path: str, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> Callable:
        self._cls = self._base_cls or cls
        return super().delete(path, **kwargs)

    def head(self, path: str, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> Callable:
        self._cls = self._base_cls or cls
        return super().head(path, **kwargs)

    def options(self, path: str, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> Callable:
        self._cls = self._base_cls or cls
        return super().options(path, **kwargs)

    def add_api_route(self, *args: Any, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> None:
        super().add_api_route(*args, **kwargs)
        self._cls = self._base_cls or cls or self._cls
        route = self.routes[-1]

        _regex_mapping.append((re.compile(route.path), route, self._cls))  # type: ignore


class FastAPIRouter(APIRouter):
    def __init__(self, include_in_app: bool = True, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if include_in_app:
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


plain_router = FrontikRouter()
router = FastAPIRouter(include_in_app=False)
not_found_router = FrontikRouter()
method_not_allowed_router = FrontikRouter()
regex_router = FrontikRegexRouter()


def _find_fastapi_route(scope: dict) -> Optional[APIRoute]:
    for route in _fastapi_routes:
        match, child_scope = route.matches(scope)
        if match == Match.FULL:
            scope.update(child_scope)
            scope['route'] = route
            return route

    return None


def _find_regex_route(
    path: str, method: str
) -> Union[tuple[APIRoute, Type[PageHandler], dict], tuple[None, None, dict]]:
    for pattern, route, cls in _regex_mapping:
        match = pattern.match(path)
        if match and next(iter(route.methods), None) == method:
            return route, cls, match.groupdict()

    return None, None, {}


def find_route(path: str, method: str) -> dict:
    route: APIRoute
    route, page_cls, path_params = _find_regex_route(path, method)  # type: ignore
    scope = {
        'type': 'http',
        'path': path,
        'method': method,
        'route': route,
        'page_cls': page_cls,
        'path_params': path_params,
    }

    if route is None:
        route, page_cls = _plain_routes.get((path.strip('/'), method), (None, None))
        scope['route'] = route
        scope['page_cls'] = page_cls

    if route is None:
        route = _find_fastapi_route(scope)

    if route is None and method == 'HEAD':
        return find_route(path, 'GET')

    if route is None:
        routing_logger.error('match for request url %s "%s" not found', method, path)

    return scope


def get_allowed_methods(path: str) -> list[str]:
    allowed_methods = []
    for method in ('GET', 'POST', 'PUT', 'DELETE', 'HEAD'):
        route, _ = _plain_routes.get((path.strip('/'), method), (None, None))
        if route is None:
            route, _, _ = _find_regex_route(path, method)

        if route is not None:
            allowed_methods.append(method)

    return allowed_methods
