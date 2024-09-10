import asyncio

from frontik.handler import PageHandler
from frontik.handler import get_current_handler
from frontik.routing import regex_router, FrontikRouter
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

router = FrontikRouter()

class Page(PageHandler):
    pass

@router.get('/suka', cls=PageHandler)
async def get_page0(self: PageHandler = get_current_handler()):
    result = await self.get_url('http://example.com', '/', request_timeout=0.001)
    # self.json.put({i: result.status_code for i in range(2_000)})
    self.json.put({123: 456})
    await self.finish(None)
