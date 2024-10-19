import asyncio
import json
import re
from typing import Any

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse
from tornado.escape import to_unicode

from frontik import media_types
from frontik.balancing_client import get_http_client
from frontik.dependencies import HttpClientT
from frontik.loggers import JSON_FORMATTER
from frontik.routing import router
from frontik.testing import FrontikTestBase
from frontik.util import any_to_bytes, any_to_unicode


def modify_http_client_request(balanced_request):
    balanced_request.headers['X-Foo'] = 'Bar'


@router.get('/http_client/custom_headers')
async def custom_headers_get_page(request: Request, http_client=Depends(get_http_client(modify_http_client_request))):
    result = await http_client.post_url(request.headers.get('host'), request.url.path)
    return result.data


@router.post('/http_client/custom_headers')
async def custom_headers_post_page(request: Request):
    return request.headers


@router.get('/http_client/fibonacci')
async def fibonacci_page(n: int, request: Request, http_client: HttpClientT):
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
async def unicode_page(request: Request, http_client: HttpClientT):
    try:
        await http_client.post_url(request.headers.get('host'), '/a-вот')
    except UnicodeEncodeError:
        return Response('UnicodeEncodeError', headers={'Content-Type': media_types.TEXT_PLAIN})


FIELDS: dict[str, Any] = {
    'fielda': 'hello',
    'fieldb': '',
    'field3': 'None',
    'field4': '0',
    'field5': 0,
    'field6': False,
    'field7': ['1', '3', 'jiji', bytes([1, 2, 3])],
}

FILES: dict[str, list] = {
    'field9': [{'filename': 'file0', 'body': b'\x10\x20\x30'}],
    'field10': [
        {'filename': 'file1', 'body': b'\x01\x02\x03'},
        {'filename': 'файл 01-12_25.abc', 'body': 'Ёконтент 123 !"№;%:?*()_+={}[]'},
    ],
}


@router.get('/http_client/post_url')
async def post_url_get_page(request: Request, http_client: HttpClientT):
    result = await http_client.post_url(request.headers.get('host'), request.url.path, data=FIELDS, files=FILES)
    if not result.failed:
        return result.data


@router.post('/http_client/post_url')
async def post_url_post_page(request: Request):
    errors_count = 0
    body_parts = (await request.body()).split(b'\r\n--')

    for part in body_parts:
        field_part = re.search(rb'name="(?P<name>.+)"\r\n\r\n(?P<value>.*)', part)
        file_part = re.search(
            rb'name="(?P<name>.+)"; filename="(?P<filename>.+)"\r\n' rb'Content-Type: \S+\r\n\r\n(?P<value>.*)', part
        )

        if field_part:
            val = field_part.group('value')
            name = any_to_unicode(field_part.group('name'))

            if (isinstance(FIELDS[name], list) and all(val != any_to_bytes(x) for x in FIELDS[name])) or (
                not isinstance(FIELDS[name], list) and any_to_bytes(FIELDS[name]) != val
            ):
                errors_count += 1

        elif file_part:
            val = file_part.group('value')
            name = any_to_unicode(file_part.group('name'))
            filename = file_part.group('filename')

            for file in FILES[name]:
                if any_to_bytes(file['filename']) == filename and any_to_bytes(file['body']) != val:
                    errors_count += 1

        elif re.search(b'name=', part):
            errors_count += 1

    return {'errors_count': errors_count}


@router.get('/http_client/parse_response')
async def parse_response_get_page(request: Request, http_client: HttpClientT):
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
async def parse_error_get_page(request: Request, http_client: HttpClientT):
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
async def post_simple_get_page(request: Request, http_client: HttpClientT):
    result = await http_client.post_url(request.headers.get('host'), request.url.path)
    return Response(result.data)


@router.post('/http_client/post_simple')
async def post_simple_post_page():
    return Response('post_url success', headers={'Content-Type': media_types.TEXT_PLAIN})


@router.get('/http_client/long_page_request')
async def long_request_page(http_client: HttpClientT, request: Request):
    result = await http_client.post_url(request.headers.get('host'), request.url.path, request_timeout=0.5)
    return {'error_received': result.failed}


class TestHttpClient(FrontikTestBase):
    async def test_post_url_simple(self):
        response = await self.fetch('/http_client/post_simple')
        assert response.raw_body == b'post_url success'

    async def test_post_url_mfd(self):
        response = await self.fetch('/http_client/post_url')
        assert response.status_code == 200
        assert response.raw_body == b'{"errors_count":0}'

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
async def long_request(http_client: HttpClientT, request: Request) -> None:
    await http_client.get_url(request.headers.get('host'), '/long_page')


class TestRequestCanceled(FrontikTestBase):
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
