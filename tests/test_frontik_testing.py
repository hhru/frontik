from lxml import etree
from tornado.ioloop import IOLoop

from frontik.app import FrontikApplication
from frontik.handler import PageHandler
from frontik.options import options
from frontik.testing import FrontikTestCase, FrontikTestBase
from frontik.util import gather_list
from tests.projects.test_app.pages.handler import delete
from tests import FRONTIK_ROOT


class AsyncHandler(PageHandler):
    async def get_page(self):
        self.result = 0

        res1, res2 = await gather_list(
            self.get_url(self.config.serviceHost, '/val1/1'),
            self.get_url(self.config.serviceHost, '/val2/2')
        )
        self.result += int(res1.data.findtext('val'))
        self.result += int(res2.data.findtext('val'))

        res = etree.Element('result')
        res.text = str(self.result)
        self.doc.put(res)
        self.set_status(400)


class CheckConfigHandler(PageHandler):
    async def get_page(self):
        self.text = self.config.config_param


class TestApplication(FrontikApplication):
    def application_urls(self):
        return [
            ('/config', CheckConfigHandler),
            ('/sum_values', AsyncHandler),
            ('/delete', delete.Page),
        ]


class TestFrontikTestingOld(FrontikTestCase):
    def setUp(self):
        options.consul_enabled = False
        super().setUp()
        self.configure_app(serviceHost='http://service.host')

    def get_app(self):
        app = TestApplication(app='test_app')

        IOLoop.current().run_sync(app.init)

        self.patch_app_http_client(app)

        return app

    def test_config(self):
        self.configure_app(config_param='param_value')
        response = self.fetch('/config')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.raw_body, b'param_value')

    def test_xml_stub(self):
        self.set_stub('http://service.host/val1/$id', response_file=f'{FRONTIK_ROOT}/tests/stub.xml', id='1', val='2')
        self.set_stub('http://service.host/val2/2', response_file=f'{FRONTIK_ROOT}/tests/stub.xml', val='3')

        doc = self.fetch_xml('/sum_values')

        self.assertEqual(doc.findtext('result'), '5')

    def test_json_stub(self):
        self.set_stub(
            f'http://127.0.0.1:{self.get_http_port()}/delete', request_method='DELETE',
            response_file=f'{FRONTIK_ROOT}/tests/stub.json', param='param'
        )

        json = self.fetch_json('/delete')
        self.assertEqual(json, {'result': 'param'})


class TestFrontikTesting(FrontikTestBase):
    def create_app(self):
        options.consul_enabled = False
        app = TestApplication(app='test_app')
        return app

    async def test_config(self):
        self.configure_app(config_param='param_value')
        response = await self.fetch('/config')

        assert response.status_code == 200
        assert response.raw_body == b'param_value'

    async def test_json_stub(self):
        self.configure_app(serviceHost='http://service.host')
        self.set_stub(
            f'http://backend/delete', request_method='DELETE',
            response_file=f'{FRONTIK_ROOT}/tests/stub.json', param='param'
        )

        json = await self.fetch_json('/delete', method='POST')
        assert json == {'result': 'param'}

    async def test_xml_stub(self):
        self.set_stub('http://service.host/val1/$id', response_file=f'{FRONTIK_ROOT}/tests/stub.xml', id='1', val='2')
        self.set_stub('http://service.host/val2/2', response_file=f'{FRONTIK_ROOT}/tests/stub.xml', val='3')

        doc = await self.fetch_xml('/sum_values')

        assert doc.findtext('result') == '5'
