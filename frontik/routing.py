import importlib
import logging
import pkgutil
import re
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any, Callable, MutableSequence, Optional, Type, Union

from fastapi import APIRouter, Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware

from frontik import request_context
from frontik.handler import PageHandler, build_error_data, get_default_headers, process_request
from frontik.options import options
from frontik.util import check_request_id, generate_uniq_timestamp_request_id

routing_logger = logging.getLogger('frontik.routing')

routers: list[APIRouter] = []
_plain_routes: dict[tuple, tuple] = {}
_regex_mapping: list[tuple[re.Pattern, APIRoute, Type[PageHandler]]] = []


class FrontikRouter(APIRouter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        routers.append(self)
        self._cls: Optional[Type[PageHandler]] = None
        self._path: Optional[str] = None

    def get(self, path: str, cls: Type[PageHandler] = PageHandler, **kwargs: Any) -> Callable:
        self._path, self._cls = path, cls
        return super().get(path, **kwargs)

    def post(self, path: str, cls: Type[PageHandler] = PageHandler, **kwargs: Any) -> Callable:
        self._path, self._cls = path, cls
        return super().post(path, **kwargs)

    def put(self, path: str, cls: Type[PageHandler] = PageHandler, **kwargs: Any) -> Callable:
        self._path, self._cls = path, cls
        return super().put(path, **kwargs)

    def delete(self, path: str, cls: Type[PageHandler] = PageHandler, **kwargs: Any) -> Callable:
        self._path, self._cls = path, cls
        return super().delete(path, **kwargs)

    def head(self, path: str, cls: Type[PageHandler] = PageHandler, **kwargs: Any) -> Callable:
        self._path, self._cls = path, cls
        return super().head(path, **kwargs)

    def add_api_route(self, *args, **kwargs):
        super().add_api_route(*args, **kwargs)
        route: APIRoute = self.routes[-1]  # type: ignore
        method = next(iter(route.methods), None)

        if _plain_routes.get((self._path, method), None) is not None:
            raise RuntimeError(f'route for {method} {self._path} exists')

        _plain_routes[(self._path, method)] = (route, self._cls)  # we need our routing, for get route object
        self._cls, self._path = None, None


class FrontikRegexRouter(APIRouter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        routers.append(self)
        self._cls: Optional[Type[PageHandler]] = None
        self._path: Optional[str] = None

    def get(self, path: str, cls: Type[PageHandler] = PageHandler, **kwargs: Any) -> Callable:
        self._path, self._cls = path, cls
        return super().get(path, **kwargs)

    def post(self, path: str, cls: Type[PageHandler] = PageHandler, **kwargs: Any) -> Callable:
        self._path, self._cls = path, cls
        return super().post(path, **kwargs)

    def put(self, path: str, cls: Type[PageHandler] = PageHandler, **kwargs: Any) -> Callable:
        self._path, self._cls = path, cls
        return super().put(path, **kwargs)

    def delete(self, path: str, cls: Type[PageHandler] = PageHandler, **kwargs: Any) -> Callable:
        self._path, self._cls = path, cls
        return super().delete(path, **kwargs)

    def head(self, path: str, cls: Type[PageHandler] = PageHandler, **kwargs: Any) -> Callable:
        self._path, self._cls = path, cls
        return super().head(path, **kwargs)

    def add_api_route(self, *args, **kwargs):
        super().add_api_route(*args, **kwargs)

        _regex_mapping.append((re.compile(self._path), self.routes[-1], self._cls))  # type: ignore

        self._cls, self._path = None, None


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


def import_all_pages(app_module: Optional[str]) -> None:
    """Import all pages on startup"""

    if app_module is None:
        return

    pages_package = importlib.import_module(f'{app_module}.pages')
    for _, name, __ in _iter_submodules(pages_package.__path__):
        full_name = pages_package.__name__ + '.' + name
        try:
            importlib.import_module(full_name)
        except ModuleNotFoundError:
            continue
        except Exception as ex:
            routing_logger.error('failed on import page %s %s', full_name, ex)
            continue


router = FrontikRouter()
regex_router = FrontikRegexRouter()
routers.extend((router, regex_router))


def _get_remote_ip(request: Request) -> str:
    ip = request.headers.get('X-Real-Ip', None) or request.headers.get('X-Forwarded-For', None)
    if ip is None and request.client:
        ip = request.client.host
    return ip or ''


def _setup_page_handler(request: Request, cls: Type[PageHandler]) -> None:
    # create legacy PageHandler and put to request
    handler = cls(
        request.app.frontik_app,
        request.query_params,
        request.cookies,
        request.headers,
        request.state.body_bytes,
        request.state.start_time,
        request.url.path,
        request.state.path_params,
        _get_remote_ip(request),
        request.method,
    )

    request.state.handler = handler


def _find_regex_route(request: Request) -> Union[tuple[APIRoute, Type[PageHandler], dict], tuple[None, None, None]]:
    for pattern, route, cls in _regex_mapping:
        match = pattern.match(request.url.path)
        if match and next(iter(route.methods), None) == request.method:
            return route, cls, match.groupdict()

    return None, None, None


def make_not_found_response(frontik_app, path):
    allowed_methods = []
    for method in ('GET', 'POST', 'PUT', 'DELETE', 'HEAD'):
        route, page_cls = _plain_routes.get((path, method), (None, None))
        if route is not None:
            allowed_methods.append(method)

    if allowed_methods:
        status = 405
        headers = get_default_headers()
        headers['Allow'] = ', '.join(allowed_methods)
        content = b''
    elif hasattr(frontik_app, 'application_404_handler'):
        status, headers, content = frontik_app.application_404_handler()
    else:
        status, headers, content = build_error_data(404, 'Not Found')

    return Response(status_code=status, headers=headers, content=content)


class RoutingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, _call_next: Callable) -> Response:
        request.state.start_time = time.time()

        routing_logger.info('requested url: %s', request.url.path)

        request_id = request.headers.get('X-Request-Id') or generate_uniq_timestamp_request_id()
        if options.validate_request_id:
            check_request_id(request_id)

        with request_context.request_context(request, request_id):
            request.state.body_bytes = await request.body()

            route: APIRoute
            route, page_cls = _plain_routes.get((request.url.path, request.method), (None, None))
            request.state.path_params = {}

            if route is None:
                route, page_cls, path_params = _find_regex_route(request)
                request.state.path_params = path_params

            if route is None:
                routing_logger.error('match for request url %s "%s" not found', request.method, request.url.path)
                return make_not_found_response(request.app.frontik_app, request.url.path)

            _setup_page_handler(request, page_cls)

            response = await process_request(request, route.get_route_handler(), route)
            return response
