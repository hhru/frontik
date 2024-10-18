from fastapi import Request, Depends
from typing import Annotated, Any
from frontik.balancing_client import get_http_client
from http_client import HttpClient


async def get_app_config(request: Request):
    return request.app.config

AppConfig = Annotated[Any, Depends(get_app_config)]
HttpClientT = Annotated[HttpClient, Depends(get_http_client())]

