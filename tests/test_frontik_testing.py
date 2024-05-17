import pytest
from lxml import etree

from frontik.app import FrontikApplication
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router
from frontik.testing import FrontikTestBase
from frontik.util import gather_list
from tests import FRONTIK_ROOT
from tests.projects.test_app.pages.handler import delete  # noqa


@router.get('/sum_values', cls=PageHandler)
async def sum_values_page(handler=get_current_handler()):
    handler.result = 0
    service_host = handler.config.serviceHost

    res1, res2 = await gather_list(handler.get_url(service_host, '/val1/1'), handler.get_url(service_host, '/val2/2'))
    handler.result += int(res1.data.findtext('val'))
    handler.result += int(res2.data.findtext('val'))

    res = etree.Element('result')
    res.text = str(handler.result)
    handler.doc.put(res)
    handler.set_status(400)


@router.get('/config', cls=PageHandler)
async def check_config_page(handler=get_current_handler()):
    handler.text = handler.config.config_param


class TestFrontikTestingOld(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication()

    @pytest.fixture(scope='class')
    def with_tornado_mocks(self):
        return True

    async def test_config(self):
        self.configure_app(config_param='param_value')
        response = await self.fetch('/config')

        assert response.status_code == 200
        assert response.raw_body == b'param_value'

    async def test_xml_stub(self):
        self.configure_app(serviceHost='http://service.host')
        self.set_stub('http://service.host/val1/$id', response_file=f'{FRONTIK_ROOT}/tests/stub.xml', id='1', val='2')
        self.set_stub('http://service.host/val2/2', response_file=f'{FRONTIK_ROOT}/tests/stub.xml', val='3')

        doc = await self.fetch_xml('/sum_values')

        assert doc.findtext('result') == '5'

    async def test_json_stub(self):
        self.configure_app(serviceHost='http://service.host')
        self.set_stub(
            f'http://127.0.0.1:{self.get_http_port()}/handler/delete',
            request_method='DELETE',
            response_file=f'{FRONTIK_ROOT}/tests/stub.json',
            param='param',
        )

        json = await self.fetch_json('/handler/delete')
        assert json == {'result': 'param'}


class TestFrontikTesting(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication()

    async def test_config(self):
        self.configure_app(config_param='param_value')
        response = await self.fetch('/config')

        assert response.status_code == 200
        assert response.raw_body == b'param_value'

    async def test_json_stub(self):
        self.configure_app(serviceHost='http://service.host')
        self.set_stub(
            'http://backend/handler/delete',
            request_method='DELETE',
            response_file=f'{FRONTIK_ROOT}/tests/stub.json',
            param='param',
        )

        json = await self.fetch_json('/handler/delete', method='POST')
        assert json == {'result': 'param'}

    async def test_xml_stub(self):
        self.configure_app(serviceHost='http://service.host')
        self.set_stub('http://service.host/val1/$id', response_file=f'{FRONTIK_ROOT}/tests/stub.xml', id='1', val='2')
        self.set_stub('http://service.host/val2/2', response_file=f'{FRONTIK_ROOT}/tests/stub.xml', val='3')

        doc = await self.fetch_xml('/sum_values')

        assert doc.findtext('result') == '5'
