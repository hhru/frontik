from typing import Annotated, Any

from fastapi import Depends, Request
from http_client import HttpClient

from frontik.app_integrations.statsd import StatsDClient
from frontik.balancing_client import get_http_client


async def get_app_config(request: Request) -> Any:
    return request.app.config


async def get_statsd_client(request: Request) -> StatsDClient:
    return request.app.statsd_client


StatsDClientT = Annotated[StatsDClient, Depends(get_statsd_client)]
AppConfig = Annotated[Any, Depends(get_app_config)]
HttpClientT = Annotated[HttpClient, Depends(get_http_client())]
