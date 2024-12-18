import contextvars
from typing import Annotated, Any

import http_client as balancing_http_client
from fastapi import Depends, Request

from frontik.app_integrations import statsd

clients: contextvars.ContextVar = contextvars.ContextVar('clients')


async def get_app_config(request: Request) -> Any:
    return request.app.config


async def get_http_client() -> balancing_http_client.HttpClient:
    return clients.get().get('http_client')


async def get_statsd_client() -> statsd.StatsDClient:
    return clients.get().get('statsd_client')


StatsDClient = Annotated[statsd.StatsDClient, Depends(get_statsd_client)]
AppConfig = Annotated[Any, Depends(get_app_config)]
HttpClient = Annotated[balancing_http_client.HttpClient, Depends(get_http_client)]
