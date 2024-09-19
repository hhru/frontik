from fastapi import Response

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router
from frontik.testing import FrontikTestBase


@plain_router.get('/cookies', cls=PageHandler)
async def cookies_page(handler: PageHandler = get_current_handler()) -> None:
    handler.set_cookie('key1', 'val1')
    handler.set_cookie('key2', 'val2')


@plain_router.get('/asgi_cookies')
async def asgi_cookies_page(response: Response) -> None:
    response.set_cookie('key1', 'val1')
    response.set_cookie('key2', 'val2')


class TestCookies(FrontikTestBase):
    async def test_cookies(self):
        response = await self.fetch('/cookies')

        assert response.status_code == 200
        assert response.headers.getall('Set-Cookie') == ['key1=val1; Path=/', 'key2=val2; Path=/']

    async def test_asgi_cookies(self):
        response = await self.fetch('/asgi_cookies')

        assert response.status_code == 200
        assert response.headers.getall('Set-Cookie') == [
            'key1=val1; Path=/; SameSite=lax',
            'key2=val2; Path=/; SameSite=lax',
        ]
