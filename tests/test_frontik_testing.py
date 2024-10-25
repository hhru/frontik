from typing import Any

from fastapi import Request, Response

from frontik.dependencies import AppConfig, HttpClient
from frontik.routing import router
from frontik.testing import FrontikTestBase
from frontik.util import gather_list
from tests import FRONTIK_ROOT


@router.get('/sum_values')
async def sum_values_page(config: AppConfig, http_client: HttpClient) -> int:
    result = 0
    service_host = config.serviceHost

    res1, res2 = await gather_list(
        http_client.get_url(service_host, '/val1/1'), http_client.get_url(service_host, '/val2/2')
    )
    result += int(res1.data.findtext('val'))
    result += int(res2.data.findtext('val'))

    return result


@router.get('/config')
async def check_config_page(config: AppConfig) -> Response:
    return Response(config.config_param)


@router.post('/json_stub')
async def post_page(request: Request, http_client: HttpClient) -> Any:
    result = await http_client.delete_url('http://backend', request.url.path, fail_fast=True)
    return result.data


class TestFrontikTesting(FrontikTestBase):
    async def test_config(self):
        self.configure_app(config_param='param_value')
        response = await self.fetch('/config')

        assert response.status_code == 200
        assert response.raw_body == b'param_value'

    async def test_json_stub(self):
        self.set_stub(
            'http://backend/json_stub',
            request_method='DELETE',
            response_file=f'{FRONTIK_ROOT}/tests/stub.json',
            param='param',
        )

        json = await self.fetch_json('/json_stub', method='POST')
        assert json == {'result': 'param'}

    async def test_xml_stub(self):
        self.configure_app(serviceHost='http://service.host')
        self.set_stub('http://service.host/val1/$id', response_file=f'{FRONTIK_ROOT}/tests/stub.xml', id='1', val='2')
        self.set_stub('http://service.host/val2/2', response_file=f'{FRONTIK_ROOT}/tests/stub.xml', val='3')

        response = await self.fetch('/sum_values')

        assert response.raw_body == b'5'
