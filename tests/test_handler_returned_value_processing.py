from __future__ import annotations

import pytest
from pydantic import BaseModel

from frontik.app import FrontikApplication
from frontik.handler import PageHandler
from frontik.testing import FrontikTestBase
from tests import FRONTIK_ROOT


class _PydanticModel(BaseModel):
    int_field: int
    bool_field: bool


class ReturnPydanticModelHandler(PageHandler):
    async def get_page(self) -> _PydanticModel:
        return _PydanticModel(int_field=1, bool_field=True)


class ReturnDictHandler(PageHandler):
    async def get_page(self) -> dict:
        return {'is_dict': True}


class TestApplication(FrontikApplication):
    def application_urls(self) -> list[tuple]:
        return [
            ('/return_dict', ReturnDictHandler),
            ('/return_pydantic', ReturnPydanticModelHandler),
        ]


class TestHandlerReturnedValuesProcessing(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> TestApplication:
        return TestApplication(app='test_app', app_root=FRONTIK_ROOT)

    async def test_get_dict(self):
        resp = await self.fetch_json('/return_dict')
        assert resp['is_dict'] is True

    async def test_get_pydantic_model(self):
        resp = await self.fetch_json('/return_pydantic')
        assert resp['int_field'] == 1
        assert resp['bool_field'] is True
