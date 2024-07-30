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

if TYPE_CHECKING:
    from frontik.handler import PageHandler

routing_logger = logging.getLogger('frontik.routing')

routers: list[APIRouter] = []
_plain_routes: dict[tuple, tuple] = {}
_regex_mapping: list[tuple[re.Pattern, APIRoute, Type[PageHandler]]] = []


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

    def add_api_route(self, *args, **kwargs):
        super().add_api_route(*args, **kwargs)
        route: APIRoute = self.routes[-1]  # type: ignore
        method = next(iter(route.methods), None)
        path = route.path.strip('/')

        if _plain_routes.get((path, method), None) is not None:
            raise RuntimeError(f'route for {method} {path} already exists')

        _plain_routes[(path, method)] = (route, self._cls)  # we need our routing, for get route object


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

    def add_api_route(self, *args: Any, cls: Optional[Type[PageHandler]] = None, **kwargs: Any) -> None:
        super().add_api_route(*args, **kwargs)
        self._cls = self._base_cls or cls or self._cls
        route = self.routes[-1]

        _regex_mapping.append((re.compile(route.path), route, self._cls))  # type: ignore


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


router = FrontikRouter()
regex_router = FrontikRegexRouter()
routers.extend((router, regex_router))


def _find_regex_route(
    path: str, method: str
) -> Union[tuple[APIRoute, Type[PageHandler], dict], tuple[None, None, None]]:
    for pattern, route, cls in _regex_mapping:
        match = pattern.match(path)
        if match and next(iter(route.methods), None) == method:
            return route, cls, match.groupdict()

    return None, None, None


def find_route(path: str, method: str) -> tuple[APIRoute, type, dict]:
    route: APIRoute
    route, page_cls, path_params = _find_regex_route(path, method)  # type: ignore

    if route is None:
        route, page_cls = _plain_routes.get((path.strip('/'), method), (None, None))
        path_params = {}

    if route is None:
        routing_logger.error('match for request url %s "%s" not found', method, path)
        return None, None, None

    return route, page_cls, path_params  # type: ignore


def get_allowed_methods(path: str) -> list[str]:
    allowed_methods = []
    for method in ('GET', 'POST', 'PUT', 'DELETE', 'HEAD'):
        route, _ = _plain_routes.get((path, method), (None, None))
        if route is not None:
            allowed_methods.append(method)

    return allowed_methods
