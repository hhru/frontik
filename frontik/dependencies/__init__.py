from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Optional, Union

import http_client
from fastapi import Depends, Request

from frontik.app_integrations import statsd

if TYPE_CHECKING:
    from frontik.app import FrontikApplication


_app_instance: Optional[FrontikApplication] = None


def get_app() -> FrontikApplication:
    assert _app_instance is not None
    return _app_instance


def set_app(app: FrontikApplication) -> None:
    global _app_instance
    _app_instance = app


def get_app_config() -> Any:
    return get_app().config


async def __get_app_config(request: Request) -> Any:
    return request.app.config


def get_http_client() -> http_client.HttpClient:
    assert get_app().http_client is not None
    return get_app().http_client


async def __get_http_client(request: Request) -> http_client.HttpClient:
    assert request.app.http_client is not None
    return request.app.http_client


def get_statsd_client() -> Union[statsd.StatsDClient, statsd.StatsDClientStub]:
    return get_app().statsd_client


async def __get_statsd_client(request: Request) -> Optional[statsd.StatsDClient]:
    return request.app.statsd_client


AppConfig = Annotated[Any, Depends(__get_app_config)]
HttpClient = Annotated[http_client.HttpClient, Depends(__get_http_client)]
StatsDClient = Annotated[statsd.StatsDClient, Depends(__get_statsd_client)]
