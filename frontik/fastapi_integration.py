import asyncio
import dataclasses
import typing
from contextlib import contextmanager
from contextvars import ContextVar
from copy import copy
from functools import wraps
from typing import Callable, Any, Awaitable, Mapping

from fastapi import params, FastAPI
from fastapi.dependencies.utils import solve_dependencies, get_dependant
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.requests import Request

from frontik.handler import PageHandler

CHARSET = "utf-8"

_current_scope = ContextVar("_current_scope")


def frontik_asgi_handler(asgi_app):
    class AsgiHandler(PageHandler):
        async def handle_request(self):
            headers = []
            for header in self.request.headers:
                for value in self.request.headers.get_list(header):
                    headers.append(
                        (header.encode(CHARSET).lower(), value.encode(CHARSET))
                    )

            scope = {
                "type": self.request.protocol,
                "http_version": self.request.version,
                "path": self.request.path,
                "method": self.request.method,
                "query_string": self.request.query.encode(CHARSET),
                "headers": headers,
                "client": (self.request.remote_ip, 0),
            }
            current_scope_token = _current_scope.set(scope)

            async def receive():
                return {
                    "body": self.request.body,
                    "type": "http.request",
                    "more_body": False,
                }

            async def send(data):
                if data["type"] == "http.response.start":
                    self.set_status(data["status"])
                    self.clear_header("content-type")
                    self.clear_header("server")
                    self.clear_header("date")
                    for h in data["headers"]:
                        if len(h) == 2:
                            self.add_header(h[0].decode(CHARSET), h[1].decode(CHARSET))
                elif data["type"] == "http.response.body":
                    self.write(data["body"])
                else:
                    raise RuntimeError(
                        f"Unsupported response type \"{data['type']}\" for asgi app"
                    )

            try:
                with override_dependency({PageHandler: self}, asgi_app):
                    await asgi_app(scope, receive, send)
            finally:
                _current_scope.reset(current_scope_token)

        async def get(self):
            await self.handle_request()

        async def post(self):
            await self.handle_request()

        async def put(self):
            await self.handle_request()

        async def delete(self):
            await self.handle_request()

    return AsgiHandler


class FrontikFastApiRoute(APIRoute):
    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs):
        @wraps(endpoint)
        async def endpoint_wrapper(*args, **kwargs):
            await asyncio.sleep(0)
            return await endpoint(*args, **kwargs)

        super().__init__(path, endpoint=endpoint_wrapper, **kwargs)


def sync_dep(func) -> params.Depends:
    return params.Depends(func)


def async_dep(func) -> params.Depends:
    @wraps(func)
    async def wrapper(*args, **kwargs):
        task = asyncio.create_task(func(*args, **kwargs))
        await asyncio.sleep(0)
        return task

    return params.Depends(wrapper)


def await_dep(dep: params.Depends) -> params.Depends:
    async def wrapper(d: Awaitable = dep):
        return await d

    return params.Depends(wrapper)


@contextmanager
def override_dependency(overrides: Mapping[Callable, Any], app: FastAPI | None = None):
    overrides_lambda = {}
    for k, v in overrides.items():
        overrides_lambda[k] = wrap_by_lambda(v)

    if app:
        old_overrides = app.dependency_overrides
        new_overrides = copy(old_overrides)
        new_overrides.update(overrides_lambda)
        app.dependency_overrides = new_overrides

    provider_old_overrides = DepsOverridesProvider.default_overrides
    provider_new_overrides = copy(provider_old_overrides)
    provider_new_overrides.update(overrides_lambda)
    DepsOverridesProvider.default_overrides = provider_new_overrides

    yield app
    if app:
        app.dependency_overrides = old_overrides
    DepsOverridesProvider.default_overrides = provider_old_overrides


@dataclasses.dataclass
class DepsOverridesProvider:
    dependency_overrides: dict[Callable[..., Any], Any] = dataclasses.field(
        default_factory=dict
    )


DepsOverridesProvider.default_overrides = {}


def wrap_by_lambda(value):
    return lambda: value


class DepBuilder:
    def __init__(self, dep: Callable[..., Any]) -> None:
        self.dep = dep
        self._path = ""
        self._scope: typing.Optional[Mapping] = _current_scope.get(None)
        self._overrides: dict[Callable[..., Any], Callable[..., Any]] = {}

    def override(self, sub_dep: Callable[..., Any], value: Any) -> "DepBuilder":
        self._overrides[sub_dep] = wrap_by_lambda(value)
        return self

    def path(self, path: str) -> "DepBuilder":
        self._path = path
        return self

    def scope(self, scope: Mapping) -> "DepBuilder":
        self._scope = scope
        return self

    async def build(self, request: Request = None):
        dependant = get_dependant(path=self._path, call=self.dep)

        all_overrides = {**DepsOverridesProvider.default_overrides, **self._overrides}
        overrides_provider = DepsOverridesProvider(dependency_overrides=all_overrides)
        if request is None:
            if self._scope is None:
                self._scope = {"type": "http", "query_string": "", "headers": []}
            request = Request(scope=self._scope)
            form = None
        else:
            form = await request.form()

        solved = await solve_dependencies(
            request=request,
            body=form,
            dependant=dependant,
            dependency_overrides_provider=overrides_provider,
        )

        values, errors, background_tasks, sub_response, dependency_cache = solved
        if errors:
            raise RequestValidationError(errors, body=form)

        return self.dep(**values)


T = typing.TypeVar("T")


async def build_dep(func: Callable[..., T], request: Request = None) -> T:
    return await DepBuilder(func).build(request)
