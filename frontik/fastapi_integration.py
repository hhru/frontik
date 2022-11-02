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



