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
    str_field: str


class ReturnPydanticModelHandler(PageHandler):
    async def get_page(self) -> _PydanticModel:
        return _PydanticModel(int_field=1, bool_field=True, str_field='Ну привет')


class ReturnDictHandler(PageHandler):
    async def get_page(self) -> dict:
        return {'is_dict': True, 'msg': 'Ну привет'}


class ReturnSelfJsonPutHandler(PageHandler):
    async def get_page(self) -> dict:
        self.json.put({'a': 'b'})
        return self.json.put({'c': 'd'})  # type: ignore[func-returns-value]


class Application(FrontikApplication):
    def application_urls(self) -> list[tuple]:
        return [
            ('/return_dict', ReturnDictHandler),
            ('/return_pydantic', ReturnPydanticModelHandler),
            ('/return_self_json_put', ReturnSelfJsonPutHandler),
        ]


class TestHandlerReturnedValuesProcessing(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> Application:
        return Application(app='test_app', app_root=FRONTIK_ROOT)

    async def test_get_dict(self):
        resp = await self.fetch_json('/return_dict')
        assert resp['is_dict'] is True
        assert resp['msg'] == 'Ну привет'

    async def test_get_pydantic_model(self):
        resp = await self.fetch_json('/return_pydantic')
        assert resp['int_field'] == 1
        assert resp['bool_field'] is True
        assert resp['str_field'] == 'Ну привет'

    async def test_return_self_json_put(self):
        resp = await self.fetch_json('/return_self_json_put')
        assert resp['a'] == 'b'
        assert resp['c'] == 'd'
