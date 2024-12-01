import contextvars
from typing import Annotated, Any

import http_client
from fastapi import Depends

from frontik.app_integrations import statsd

clients: contextvars.ContextVar = contextvars.ContextVar('clients')


async def _get_app_config() -> Any:
    return clients.get().get('app_config')


async def _get_http_client() -> http_client.HttpClient:
    return clients.get().get('http_client')


async def _get_statsd_client() -> statsd.StatsDClient:
    return clients.get().get('statsd_client')


StatsDClient = Annotated[statsd.StatsDClient, Depends(_get_statsd_client)]
AppConfig = Annotated[Any, Depends(_get_app_config)]
HttpClient = Annotated[http_client.HttpClient, Depends(_get_http_client)]
