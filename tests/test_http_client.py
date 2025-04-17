import asyncio
import json

import pytest
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from tornado.escape import to_unicode

from frontik import media_types
from frontik.app import FrontikApplication
from frontik.dependencies import HttpClient
from frontik.loggers import JSON_FORMATTER
from frontik.routing import router
from frontik.testing import FrontikTestBase


@router.get('/http_client/custom_headers')
async def custom_headers_get_page(request: Request, http_client: HttpClient):
    result = await http_client.post_url(request.headers.get('host'), request.url.path)
    return result.data


@router.post('/http_client/custom_headers')
async def custom_headers_post_page(request: Request):
    return request.headers


@router.get('/http_client/fibonacci')
async def fibonacci_page(n: int, request: Request, http_client: HttpClient):
    if n < 2:
        return Response('1', headers={'Content-Type': media_types.TEXT_PLAIN})

    acc = 0

    r1, r2 = await asyncio.gather(
        http_client.get_url(request.headers.get('host'), request.url.path, data={'n': str(n - 1)}),
        http_client.get_url(request.headers.get('host'), request.url.path, data={'n': str(n - 2)}),
    )
    acc += int(r1.data)
    acc += int(r2.data)
    return Response(str(acc), headers={'Content-Type': media_types.TEXT_PLAIN})


@router.get('/http_client/raise_error')
async def unicode_page(request: Request, http_client: HttpClient):
    try:
        await http_client.post_url(request.headers.get('host'), '/a-вот')
    except UnicodeEncodeError:
        return Response('UnicodeEncodeError', headers={'Content-Type': media_types.TEXT_PLAIN})


@router.get('/http_client/parse_response')
async def parse_response_get_page(request: Request, http_client: HttpClient):
    res = {}
    result = await http_client.post_url(request.headers.get('host'), request.url.path, parse_on_error=True)
    res.update(result.data)
    result = await http_client.put_url(request.headers.get('host'), request.url.path, parse_on_error=False)
    res.update(result.to_dict())

    result = await http_client.delete_url(request.headers.get('host'), request.url.path, parse_response=False)
    if not result.failed:
        res.update({'delete': to_unicode(result.data)})

    return res


@router.post('/http_client/parse_response')
async def parse_response_post_page():
    return JSONResponse({'post': True}, 400)


@router.put('/http_client/parse_response')
async def parse_response_put_page():
    return JSONResponse({'put': True}, 400)


@router.delete('/http_client/parse_response')
async def parse_response_delete_page():
    return Response('deleted')


@router.get('/http_client/parse_error')
async def parse_error_get_page(request: Request, http_client: HttpClient):
    el_result = await http_client.post_url(request.headers.get('host'), request.url.path + '?mode=xml')
    element = el_result.data
    if element is not None:
        raise AssertionError()

    result = await http_client.post_url(request.headers.get('host'), request.url.path + '?mode=json')
    if result.failed:
        return Response('Parse error occured')
    else:
        raise AssertionError()


@router.post('/http_client/parse_error')
async def parse_error_post_page(mode: str):
    if mode == 'xml':
        return Response("""<doc frontik="tr"ue">this is broken xml</doc>""", headers={'Content-Type': 'xml'})
    elif mode == 'json':
        return Response("""{"hel"lo" : "this is broken json"}""", headers={'Content-Type': 'json'})


@router.get('/http_client/post_simple')
async def post_simple_get_page(request: Request, http_client: HttpClient):
    result = await http_client.post_url(request.headers.get('host'), request.url.path)
    return Response(result.data)


@router.post('/http_client/post_simple')
async def post_simple_post_page():
    return Response('post_url success', headers={'Content-Type': media_types.TEXT_PLAIN})


@router.get('/http_client/long_page_request')
async def long_request_page(request: Request, http_client: HttpClient):
    result = await http_client.post_url(request.headers.get('host'), request.url.path, request_timeout=0.5)
    return {'error_received': result.failed}


def modify_http_client_request(balanced_request):
    balanced_request.headers['X-Foo'] = 'Bar'


class HttpclientHookMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        scope['_http_client_hook'] = modify_http_client_request
        await self.app(scope, receive, send)


class ApplicationWithHttpClientHook(FrontikApplication):
    def __init__(self):
        super().__init__(app_module_name=None)
        self.add_middleware(HttpclientHookMiddleware)


class TestHttpClient(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return ApplicationWithHttpClientHook()

    async def test_post_url_simple(self):
        response = await self.fetch('/http_client/post_simple')
        assert response.raw_body == b'post_url success'

    async def test_fib0(self):
        response = await self.fetch('/http_client/fibonacci?n=0')
        assert response.raw_body == b'1'

    async def test_fib2(self):
        response = await self.fetch('/http_client/fibonacci?n=2')
        assert response.raw_body == b'2'

    async def test_fib6(self):
        response = await self.fetch('/http_client/fibonacci?n=6')
        assert response.raw_body == b'13'

    async def test_timeout(self):
        json = await self.fetch_json('/http_client/long_page_request')
        assert json == {'error_received': True}

    async def test_parse_error(self):
        response = await self.fetch('/http_client/parse_error')
        assert response.raw_body == b'Parse error occured'

    async def test_parse_response(self):
        json_body = await self.fetch_json('/http_client/parse_response')
        assert json_body == {'post': True, 'delete': 'deleted', 'error': {'reason': 'Bad Request', 'code': 400}}

    async def test_custom_headers(self):
        json_body = await self.fetch_json('/http_client/custom_headers')
        assert json_body['x-foo'] == 'Bar'  # fastapi makes headers names in lower case for some reason

    async def test_http_raise_error(self):
        response = await self.fetch('/http_client/raise_error')
        assert response.status_code == 200


@router.get('/long_page')
async def long_page() -> None:
    await asyncio.sleep(1)


@router.get('/long_request')
async def long_request(request: Request, http_client: HttpClient) -> None:
    await http_client.get_url(request.headers.get('host'), '/long_page')


class TestRequestCanceled(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

    async def test_request_canceled(self, caplog):
        caplog.handler.setFormatter(JSON_FORMATTER)
        response = await self.fetch('/long_request', request_timeout=0.1)
        await asyncio.sleep(2)

        assert response.status_code == 599

        for log_row in caplog.text.split('\n'):
            if log_row == '':
                continue
            log_obj = json.loads(log_row)
            assert log_obj.get('lvl') != 'ERROR', log_obj
