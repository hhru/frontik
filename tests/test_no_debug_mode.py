import http
from typing import Optional

import pytest
from fastapi import HTTPException, Request

from frontik.app import FrontikApplication
from frontik.auth import check_debug_auth_by_headers
from frontik.options import options
from frontik.routing import router
from frontik.testing import FrontikTestBase
from tests import create_basic_auth_header


@router.get('/simple')
async def get_page1() -> str:
    return 'ok'


@router.get('/basic_auth')
async def get_page2(request: Request) -> dict:
    def check_debug_auth_or_finish(login: str, password: str) -> None:
        if options.debug:
            return
        _login: Optional[str] = login or options.debug_login
        _password: Optional[str] = password or options.debug_password
        fail_header = check_debug_auth_by_headers(request.headers, _login, _password)
        if fail_header:
            raise HTTPException(
                status_code=http.client.UNAUTHORIZED, detail='Unauthorized', headers={'WWW-Authenticate': fail_header}
            )

    check_debug_auth_or_finish('user', 'god')
    return {'authenticated': True}


class TestNonDebugMode(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        options.debug = False
        options.debug_login = 'user'
        options.debug_password = 'god'
        return FrontikApplication()

    async def test_simple(self):
        response = await self.fetch('/simple')
        assert 'ok' == response.data

    async def test_basic_auth_fail(self):
        response = await self.fetch('/basic_auth')
        assert response.status_code == 401

    async def test_basic_auth_fail_on_wrong_pass(self):
        response = await self.fetch(
            '/basic_auth',
            headers={'Authorization': create_basic_auth_header('user:bad')},
        )

        assert response.status_code == 401

    async def test_basic_auth_pass(self):
        response = await self.fetch(
            '/basic_auth',
            headers={'Authorization': create_basic_auth_header('user:god')},
        )

        assert response.status_code == 200
        assert response.data == {'authenticated': True}
