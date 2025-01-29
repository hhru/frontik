from typing import Annotated, Any, Optional, Union

import http_client
from fastapi import Depends, Request

from frontik.app import FrontikApplication, app_holder
from frontik.app_integrations import statsd


def get_app() -> FrontikApplication:
    return app_holder.get()


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
