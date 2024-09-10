import asyncio

from frontik.handler import PageHandler
from frontik.handler import get_current_handler
from frontik.routing import regex_router, FrontikRouter, router, plain_router
from fastapi import Request, Response
import orjson
from fastapi.encoders import jsonable_encoder
from frontik.media_types import APPLICATION_JSON
import json
from pydantic import BaseModel
from fastapi import Form, Body
# from cachetools import TTLCache
from random import randint
from fastapi import Depends
from lxml import etree
from frontik.balancing_client import HttpClientT
import os
from frontik.handler import FinishWithPostprocessors
from http_client.request_response import FailFastError
from frontik.json_builder import JsonBuilderT



class Page(PageHandler):
    pass


# @plain_router.get('/qqpage', cls=Page)
# async def get_page0(self: Page = get_current_handler()):
#     res = await self.get_url('http://example.com', '/')
#     self.json.put({123: 456})


@router.get('/qqpage')
async def get_page0(http_client: HttpClientT, json_builder: JsonBuilderT):
    await http_client.get_url('http://example.com', '/')
    json_builder.put({123: '789'})
    return {123: '456'}

